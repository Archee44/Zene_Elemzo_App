from __future__ import annotations

import os
from typing import Dict, List, Optional
import numpy as np

try:
    import essentia
    import essentia.standard as es
except ImportError:
    es = None
from backend.services.log_filter import run_quietly
from backend.services.audio_loader import load_mono

MODEL_DIR = os.getenv('ESSENTIA_MODEL_DIR', '/app/models')
DISCOGS_DIR = os.path.join(MODEL_DIR, 'discogs400')
ENGAGE_DIR = os.path.join(MODEL_DIR, 'engagement')
_EFFNET_PRED = None
_HEAD_CACHE = {}

def _first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

def _find_head_files() -> Optional[Dict[str, str]]:
    if not os.path.isdir(ENGAGE_DIR):
        return None
    candidates = []
    for name in os.listdir(ENGAGE_DIR):
        if name.endswith('.pb') and 'engagement' in name:
            lower = name.lower()
            kind = 'regression' if 'regression' in lower else ('3c' if '3c' in lower else ('2c' if '2c' in lower else 'cls'))
            pb = os.path.join(ENGAGE_DIR, name)
            base = name.rsplit('.', 1)[0]
            json_match = os.path.join(ENGAGE_DIR, base + '.json')
            json_any = None
            for j in os.listdir(ENGAGE_DIR):
                if j.endswith('.json') and 'engagement' in j:
                    json_any = os.path.join(ENGAGE_DIR, j)
                    if j == base + '.json':
                        json_match = json_any
                        break
            candidates.append({'pb': pb, 'json': json_match if os.path.exists(json_match) else json_any, 'kind': kind})
    for pref in ('regression', '3c', '2c', 'cls'):
        for c in candidates:
            if c['kind'] == pref:
                return c
    return None

def _load_effnet() -> Optional[es.TensorflowPredictEffnetDiscogs]:
    effnet_candidates = [
        os.path.join(DISCOGS_DIR, 'discogs-effnet-bs64-1.pb'),
        os.path.join(DISCOGS_DIR, 'discogs-effnet-bs64.pb'),
    ]
    effnet_pb = _first_existing(effnet_candidates)
    if not effnet_pb:
        return None
    global _EFFNET_PRED
    if _EFFNET_PRED is None:
        _EFFNET_PRED = es.TensorflowPredictEffnetDiscogs(
            graphFilename=effnet_pb,
            output="PartitionedCall:1"
        )
    return _EFFNET_PRED

def predict_engagement(filename: str) -> Optional[Dict]:
    if es is None:
        return None
    head = _find_head_files()
    if not head:
        return None
    try:
        audio = load_mono(filename, sample_rate=16000)
        if isinstance(audio, (list, tuple)):
            audio = np.asarray(audio)
        max_len = 60 * 16000
        if len(audio) > max_len:
            audio = audio[:max_len]

        effnet = _load_effnet()
        if effnet is None:
            return None
        emb = run_quietly(effnet, audio)
        emb_np = np.asarray(emb)
        if emb_np.ndim == 1:
            emb_np = emb_np.reshape(1, -1)

        io_candidates = [
            ("serving_default_model_Placeholder", "PartitionedCall:0"),
            ("model/Placeholder", "model/Softmax"),
            ("Placeholder", "model/Softmax"),
            ("model/Placeholder", "Identity"),
            ("serving_default_model_Placeholder", "Identity:0"),
            ("Placeholder", "Identity"),
            ("serving_default_input", "StatefulPartitionedCall:0"),
        ]
        last_err = None
        out = None
        clf = _HEAD_CACHE.get(head['pb'])
        if clf is not None:
            try:
                out = run_quietly(clf, emb_np)
            except Exception:
                clf = None
        if clf is None:
            for inp_name, out_name in io_candidates:
                try:
                    clf = es.TensorflowPredict2D(graphFilename=head['pb'], input=inp_name, output=out_name)
                    out = clf(emb_np)
                    _HEAD_CACHE[head['pb']] = clf
                    break
                except Exception as e:
                    last_err = e
                    continue
        if out is None:
            raise last_err or RuntimeError('No valid IO nodes for engagement head')

        out_np = np.asarray(out)
        if out_np.ndim == 2:
            out_vec = out_np.mean(axis=0)
        else:
            out_vec = out_np
        out_vec = np.asarray(out_vec).ravel()

        kind = head['kind']
        model_name = f"engagement-{kind}"

        if kind == 'regression':
            score = float(out_vec[0]) if out_vec.size > 0 else None
            return { 'model_name': model_name, 'type': 'regression', 'score': score, 'top': None, 'candidates': [] }
        else:
            labels: List[str] = []
            if head['json'] and os.path.exists(head['json']):
                try:
                    import json as _json
                    with open(head['json'], 'r', encoding='utf-8') as f:
                        meta = _json.load(f)
                    labels = [str(c) for c in (meta.get('classes') or [])]
                except Exception:
                    labels = []
            if not labels:
                labels = [f'class_{i}' for i in range(out_vec.size)]
            L = min(len(labels), out_vec.size)
            pairs = [(labels[i], float(out_vec[i])) for i in range(L)]
            pairs.sort(key=lambda x: x[1], reverse=True)
            top = pairs[0][0] if pairs else None
            return { 'model_name': model_name, 'type': 'classification', 'top': top, 'candidates': pairs, 'score': None }
    except Exception as e:
        print('[engagement_model] inference error:', str(e))
        return None
