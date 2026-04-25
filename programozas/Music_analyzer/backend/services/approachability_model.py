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
APPROACH_DIR = os.path.join(MODEL_DIR, 'approachability')

def _first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

def _find_head_files() -> Optional[Dict[str, str]]:
    """Try to find an approachability head and its labels.

    Priority: 3-class -> 2-class -> regression. Returns dict with keys
    { 'pb': path, 'json': path or None, 'kind': '3c'|'2c'|'regression' } or None.
    """
    if not os.path.isdir(APPROACH_DIR):
        return None

    candidates = []
    for name in os.listdir(APPROACH_DIR):
        if name.endswith('.pb') and 'approachability' in name:
            lower = name.lower()
            kind = 'regression' if 'regression' in lower else ('3c' if '3c' in lower else ('2c' if '2c' in lower else None))
            if not kind:
                continue
            pb = os.path.join(APPROACH_DIR, name)
            base = name.rsplit('.', 1)[0]
            json_match = os.path.join(APPROACH_DIR, base + '.json')
            json_any = None
            for j in os.listdir(APPROACH_DIR):
                if j.endswith('.json') and 'approachability' in j:
                    json_any = os.path.join(APPROACH_DIR, j)
                    if j == base + '.json':
                        json_match = json_any
                        break
            candidates.append({'pb': pb, 'json': json_match if os.path.exists(json_match) else json_any, 'kind': kind})

    for pref in ('3c', '2c', 'regression'):
        for c in candidates:
            if c['kind'] == pref:
                return c
    return None

_EFFNET_PRED = None
_HEAD_CACHE = {}

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

def predict_approachability(filename: str) -> Optional[Dict]:
    """Run approachability head on EffNet embeddings.

    Returns:
      {
        'model_name': 'approachability-<kind>',
        'type': 'classification' | 'regression',
        'top': str | None,
        'candidates': [(label, score), ...]  # for classification
        'score': float | None,               # for regression
      }
    """
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
            ("serving_default_input_1", "StatefulPartitionedCall:0"),
        ]

        last_err = None
        out = None
        used_pair = None
        clf = _HEAD_CACHE.get(head['pb'])
        if clf is not None:
            try:
                out = run_quietly(clf, emb_np)
            except Exception:
                clf = None
        if clf is None:
            for inp_name, out_name in io_candidates:
                try:
                    clf = es.TensorflowPredict2D(
                        graphFilename=head['pb'],
                        input=inp_name,
                        output=out_name,
                    )
                    out = clf(emb_np)
                    used_pair = (inp_name, out_name)
                    _HEAD_CACHE[head['pb']] = clf
                    break
                except Exception as e:
                    last_err = e
                    continue
        if out is None:
            raise last_err or RuntimeError("No valid input/output nodes matched for approachability head")
        out_np = np.asarray(out)
        if out_np.ndim == 2:
            out_vec = out_np.mean(axis=0)
        else:
            out_vec = out_np
        out_vec = np.asarray(out_vec).ravel()

        kind = head['kind']
        model_name = f"approachability-{kind}"

        if kind in ('3c', '2c'):
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
                if out_vec.size == 3:
                    labels = ['low', 'medium', 'high']
                elif out_vec.size == 2:
                    labels = ['low', 'high']
                else:
                    labels = [f'class_{i}' for i in range(out_vec.size)]
            L = min(len(labels), out_vec.size)
            pairs = [(labels[i], float(out_vec[i])) for i in range(L)]
            pairs.sort(key=lambda x: x[1], reverse=True)
            top = pairs[0][0] if pairs else None
            return {
                'model_name': model_name,
                'type': 'classification',
                'top': top,
                'candidates': pairs,
                'score': None,
            }
        else:
            score = float(out_vec[0]) if out_vec.size > 0 else None
            return {
                'model_name': model_name,
                'type': 'regression',
                'top': None,
                'candidates': [],
                'score': score,
            }
    except Exception as e:
        print('[approachability_model] inference error:', str(e))
        return None
