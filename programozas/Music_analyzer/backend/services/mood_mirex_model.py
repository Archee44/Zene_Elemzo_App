from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import essentia
    import essentia.standard as es
except ImportError:
    es = None
from backend.services.log_filter import run_quietly
from backend.services.audio_loader import load_mono

MODEL_DIR = os.getenv('ESSENTIA_MODEL_DIR', '/app/models')
VGGISH_DIR = os.path.join(MODEL_DIR, 'vggish')
MIREX_DIR = os.path.join(MODEL_DIR, 'mood_mirex')

_MIREX_IO_CACHE: Optional[Tuple[str, str]] = None

def _first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

def _find_any_pb(root: str, must_contain: List[str]) -> Optional[str]:
    try:
        for name in os.listdir(root):
            low = name.lower()
            if not low.endswith('.pb'):
                continue
            if all(s in low for s in must_contain):
                return os.path.join(root, name)
    except Exception:
        pass
    return None

def _matching_json(pb_path: Optional[str]) -> Optional[str]:
    if not pb_path:
        return None
    base = os.path.splitext(os.path.basename(pb_path))[0]
    root = os.path.dirname(pb_path)
    cand = os.path.join(root, base + '.json')
    if os.path.exists(cand):
        return cand
    try:
        for name in os.listdir(root):
            if name.lower().endswith('.json'):
                return os.path.join(root, name)
    except Exception:
        pass
    return None

def _prepare_audio_16k(filename: str) -> np.ndarray:
    audio = load_mono(filename, sample_rate=16000)
    if isinstance(audio, (list, tuple)):
        audio = np.asarray(audio)
    max_len = 60 * 16000
    if audio.shape[0] > max_len:
        audio = audio[:max_len]
    return audio.astype(np.float32)

def _load_vggish() -> Optional[es.TensorflowPredictVGGish]:
    if es is None:
        return None
    cand = _first_existing([
        os.path.join(VGGISH_DIR, 'audioset-vggish-1.pb'),
        os.path.join(VGGISH_DIR, 'audioset-vggish-3.pb'),
        os.path.join(VGGISH_DIR, 'vggish-1.pb'),
        os.path.join(VGGISH_DIR, 'vggish.pb'),
    ])
    if not cand:
        print('[mood_mirex_model] VGGish backbone not found')
        return None
    io_pairs: List[Tuple[Optional[str], Optional[str]]] = []
    if _MIREX_IO_CACHE:
        io_pairs.append(_MIREX_IO_CACHE)
    io_pairs.extend([
        (None, None),
        ('model/Placeholder', 'model/embeddings'),
        ('model/Placeholder', 'model/vggish/embeddings'),
        ('model/Placeholder', 'model/vggish/fc2/Relu'),
    ])
    last_err = None
    for inp, out in io_pairs:
        try:
            if inp is None and out is None:
                predictor = es.TensorflowPredictVGGish(graphFilename=cand)
            else:
                predictor = es.TensorflowPredictVGGish(graphFilename=cand, input=inp, output=out)
            if inp is not None and out is not None:
                globals()['_MIREX_IO_CACHE'] = (inp, out)
            return predictor
        except Exception as e:
            last_err = e
            continue
    print('[mood_mirex_model] VGGish init failed with last error:', str(last_err))
    return None

def predict_mood_mirex(filename: str) -> Optional[Dict]:
    """Predict Mood MIREX (5-class) with VGGish backbone.

    Returns { 'model_name': str, 'top': str, 'candidates': [(label, score), ...] }
    """
    if es is None:
        return None
    if not hasattr(es, 'TensorflowPredictVGGish') or not hasattr(es, 'TensorflowPredict'):
        print('[mood_mirex_model] Required Essentia TF wrappers not available')
        return None

    head_pb = _first_existing([
        os.path.join(MIREX_DIR, 'moods_mirex-audioset-vggish-1.pb'),
        os.path.join(MIREX_DIR, 'moods_mirex-vggish-audioset-1.pb'),
    ]) or _find_any_pb(MIREX_DIR, ['mirex', 'vggish'])
    if not head_pb:
        print('[mood_mirex_model] no MIREX VGGish head found in', MIREX_DIR)
        return None
    else:
        print('[mood_mirex_model] using head file:', head_pb)
    head_json = _first_existing([
        os.path.join(MIREX_DIR, 'moods_mirex-audioset-vggish-1.json'),
        os.path.join(MIREX_DIR, 'moods_mirex-vggish-audioset-1.json'),
    ]) or _matching_json(head_pb)

    vgg = _load_vggish()
    if vgg is None:
        return None

    try:
        x = _prepare_audio_16k(filename)
        emb = run_quietly(vgg, x)
        emb_np = np.asarray(emb)
        if emb_np.ndim == 1:
            emb_np = emb_np.reshape(1, -1)
        T = emb_np.shape[0]
        need = 48
        if T >= need:
            start = (T - need) // 2
            chunk = emb_np[start:start + need, :]
        else:
            pad_frames = need - T
            chunk = np.pad(emb_np, ((pad_frames // 2, pad_frames - pad_frames // 2), (0, 0)), mode='constant')
        flat = chunk.reshape(1, -1)                     
        emb_np = flat.astype(np.float32)

        io_candidates: List[Tuple[str, str]] = []
        if globals().get('_MIREX_IO_CACHE'):
            io_candidates.append(globals()['_MIREX_IO_CACHE'])
        io_candidates.extend([
            ('model/Placeholder', 'model/Softmax'),
            ('model/Placeholder', 'model/prediction'),
            ('model/Placeholder', 'model/fully_connected/Relu'),
            ('model/Placeholder', 'model/logits_1'),
        ])

        out = None
        last_err = None
        for inp, outn in io_candidates:
            try:
                clf = es.TensorflowPredict2D(graphFilename=head_pb, input=inp, output=outn)
                out = run_quietly(clf, emb_np)
                print(f"[mood_mirex_model] matched io: input='{inp}', output='{outn}'")
                break
            except Exception as e:
                last_err = e
                continue
        if out is None:
            print('[mood_mirex_model] head run failed:', str(last_err))
            return None

        vec = np.asarray(out)
        if vec.ndim == 2:
            vec = vec.mean(axis=0)
        vec = np.asarray(vec).ravel()

        labels: List[str] = []
        if head_json and os.path.exists(head_json):
            try:
                import json as _json
                with open(head_json, 'r', encoding='utf-8') as f:
                    meta = _json.load(f)
                labels = [str(c) for c in (meta.get('classes') or [])]
            except Exception:
                labels = []
        if not labels:
            labels = ['cluster1', 'cluster2', 'cluster3', 'cluster4', 'cluster5']

        L = min(len(labels), vec.size)
        pairs = [(labels[i], float(vec[i])) for i in range(L)]
        pairs.sort(key=lambda x: x[1], reverse=True)
        top = pairs[0][0] if pairs else None
        return {
            'model_name': 'moods_mirex-audioset-vggish-1',
            'top': top,
            'candidates': pairs,
        }
    except Exception as e:
        print('[mood_mirex_model] inference error:', str(e))
        return None
