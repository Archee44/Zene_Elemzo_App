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
VA_DIR = os.path.join(MODEL_DIR, 'valence_arousal')

_VA_IO_CACHE: Optional[Tuple[str, str]] = None

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
        print('[valence_arousal_model] VGGish backbone not found')
        return None
    io_pairs: List[Tuple[Optional[str], Optional[str]]] = []
    if _VA_IO_CACHE:
        io_pairs.append(_VA_IO_CACHE)
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
                globals()['_VA_IO_CACHE'] = (inp, out)
            return predictor
        except Exception as e:
            last_err = e
            continue
    print('[valence_arousal_model] VGGish init failed with last error:', str(last_err))
    return None

def predict_valence_arousal(filename: str) -> Optional[Dict]:
    """Predict arousal/valence using VGGish backbone + DEAM head.

    Returns:
      { 'model_name': str, 'arousal': float, 'valence': float }
    or None if unavailable.
    """
    if es is None:
        return None
    if not hasattr(es, 'TensorflowPredictVGGish') or not hasattr(es, 'TensorflowPredict'):
        print('[valence_arousal_model] Required Essentia TF wrappers not available')
        return None

    head_pb = _first_existing([
        os.path.join(VA_DIR, 'deam-audioset-vggish-2.pb'),
        os.path.join(VA_DIR, 'deam-audioset-vggish-1.pb'),
    ]) or _find_any_pb(VA_DIR, ['deam', 'vggish'])
    if not head_pb:
        print('[valence_arousal_model] no DEAM VGGish head found in', VA_DIR)
        return None
    else:
        print('[valence_arousal_model] using head file:', head_pb)

    vgg = _load_vggish()
    if vgg is None:
        return None

    try:
        x = _prepare_audio_16k(filename)
        emb = run_quietly(vgg, x)
        emb_np = np.asarray(emb)
        if emb_np.ndim == 1:
            emb_np = emb_np.reshape(1, -1)

        io_candidates: List[Tuple[str, str]] = [
            ('serving_default_model_Placeholder', 'StatefulPartitionedCall'),
            ('serving_default_model_Placeholder', 'StatefulPartitionedCall:0'),
            ('serving_default_model_Placeholder', 'PartitionedCall'),
            ('serving_default_model_Placeholder', 'PartitionedCall:0'),
            ('flatten_in_input', 'dense_out'),
            ('flatten_in_input', 'onnx_tf_prefix_dense_out'),
            ('onnx_tf_prefix_flatten_in/Reshape', 'dense_out'),
        ]

        out = None
        last_err = None
        clf = None
        for inp, outn in io_candidates:
            try:
                clf = es.TensorflowPredict2D(graphFilename=head_pb, input=inp, output=outn)
                test_slice = emb_np[: max(1, emb_np.shape[0] // 6), :]
                _ = run_quietly(clf, test_slice)
                print(f"[valence_arousal_model] matched io: input='{inp}', output='{outn}'")
                break
            except Exception as e:
                last_err = e
                clf = None
                continue
        if clf is None:
            print('[valence_arousal_model] head run failed:', str(last_err))
            return None

        T = emb_np.shape[0]
        win_count = 6
        if T < win_count:
            win_count = max(1, T)
        seg_len = max(1, T // win_count)
        vals = []
        for i in range(win_count):
            start = i * seg_len
            end = T if i == win_count - 1 else min(T, (i + 1) * seg_len)
            if end <= start:
                continue
            seg = emb_np[start:end, :]
            vec = np.asarray(run_quietly(clf, seg))
            if vec.ndim == 2:
                vec = vec.mean(axis=0)
            vec = np.asarray(vec).ravel()
            if vec.size >= 2:
                a_raw, v_raw = float(vec[0]), float(vec[1])
                def _to01(x: float) -> float:
                    if 0.0 <= x <= 1.0:
                        return x
                    if -1.25 <= x <= 1.25:
                        x = (x + 1.0) / 2.0
                        return float(min(max(x, 0.0), 1.0))
                    import math
                    x = 1.0 / (1.0 + math.exp(-x))
                    return float(min(max(x, 0.0), 1.0))
                vals.append((_to01(a_raw), _to01(v_raw)))

        if not vals:
            return None
        arr = np.asarray(vals, dtype=float)
        a_med = float(np.median(arr[:, 0]))
        v_med = float(np.median(arr[:, 1]))
        a_std = float(np.std(arr[:, 0]))
        v_std = float(np.std(arr[:, 1]))
        return {
            'model_name': 'deam-audioset-vggish',
            'arousal': a_med,
            'valence': v_med,
            'arousal_std': a_std,
            'valence_std': v_std,
            'count': int(arr.shape[0]),
        }
        return None
    except Exception as e:
        print('[valence_arousal_model] inference error:', str(e))
        return None
