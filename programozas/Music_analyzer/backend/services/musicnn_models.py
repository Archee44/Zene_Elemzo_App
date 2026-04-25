from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import essentia
    import essentia.standard as es
except ImportError:
    es = None

MODEL_DIR = os.getenv('ESSENTIA_MODEL_DIR', '/app/models')
MUSICNN_DIR = os.path.join(MODEL_DIR, 'musicnn')
VGGISH_DIR = os.path.join(MODEL_DIR, 'vggish')
VA_DIR = os.path.join(MODEL_DIR, 'valence_arousal')
MIREX_DIR = os.path.join(MODEL_DIR, 'mood_mirex')

def _exists(p: Optional[str]) -> bool:
    return bool(p) and os.path.exists(p)                

def _first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if _exists(p):
            return p
    return None

def _load_musicnn() -> Optional[es.TensorflowPredictMusiCNN]:
    if es is None:
        return None
    pb = _first_existing([
        os.path.join(MUSICNN_DIR, 'msd-musicnn-1.pb'),
    ])
    if not pb:
        return None
    try:
        return es.TensorflowPredictMusiCNN(graphFilename=pb)
    except Exception:
        io_candidates: List[Tuple[str, str]] = [
            ("model/Placeholder", "model/embedding"),
            ("Placeholder", "model/embedding"),
            ("serving_default_model_Placeholder", "Identity:0"),
        ]
        last = None
        for inp, out in io_candidates:
            try:
                return es.TensorflowPredictMusiCNN(graphFilename=pb, input=inp, output=out)                
            except Exception as e:
                last = e
                continue
        raise last or RuntimeError('Cannot configure MusiCNN backbone')

def _prepare_audio_16k(filename: str) -> np.ndarray:
    audio = es.MonoLoader(filename=filename, sampleRate=16000)()
    if isinstance(audio, (list, tuple)):
        audio = np.asarray(audio)
    max_len = 60 * 16000
    if audio.shape[0] > max_len:
        audio = audio[:max_len]
    return audio.astype(np.float32)

def _load_vggish() -> Optional[es.TensorflowPredictVGGish]:
    if es is None:
        return None
    pb = _first_existing([
        os.path.join(VGGISH_DIR, 'audioset-vggish-1.pb'),
        os.path.join(VGGISH_DIR, 'audioset-vggish-3.pb'),                    
        os.path.join(VGGISH_DIR, 'vggish-1.pb'),
        os.path.join(VGGISH_DIR, 'vggish.pb'),
    ])
    if not pb:
        return None
    try:
        return es.TensorflowPredictVGGish(graphFilename=pb)
    except Exception:
        return None

def predict_valence_arousal(filename: str) -> Optional[Dict]:
    """Use MusiCNN backbone + DEAM head to estimate arousal/valence (0..1).

    Returns {'model_name': 'deam-msd-musicnn-1', 'arousal': float, 'valence': float}
    or None if unavailable.
    """
    if es is None:
        return None
    head_pb_musicnn = None
    musicnn = None

    def _run_with_head(_head_pb: str, embedder) -> Optional[Dict]:
        print(f"[va] using head: {_head_pb}")
        x = _prepare_audio_16k(filename)
        emb = embedder(x)
        emb_np = np.asarray(emb)
        if emb_np.ndim == 1:
            emb_np = emb_np.reshape(1, -1)
        io_candidates = [
            ("serving_default_model_Placeholder", "StatefulPartitionedCall"),
            ("serving_default_model_Placeholder", "StatefulPartitionedCall:0"),
            ("serving_default_model_Placeholder", "StatefulPartitionedCall_1"),
            ("serving_default_model_Placeholder", "StatefulPartitionedCall_1:0"),
            ("flatten_in_input", "dense_out"),
            ("flatten_in_input", "onnx_tf_prefix_dense_out"),
            ("onnx_tf_prefix_flatten_in/Reshape", "dense_out"),
        ]
        out = None
        last = None
        for inp, outn in io_candidates:
            try:
                clf = es.TensorflowPredict2D(graphFilename=_head_pb, input=inp, output=outn)
                out = clf(emb_np)
                print(f"[va] matched io nodes: input='{inp}', output='{outn}'")
                break
            except Exception as e:
                if last is None:
                    print(f"[va] io pair failed (input='{inp}', output='{outn}') -> {e}")
                last = e
                continue
        if out is None:
            raise last or RuntimeError('Cannot run DEAM head')
        vec = np.asarray(out)
        if vec.ndim == 2:
            vec = vec.mean(axis=0)
        vec = np.asarray(vec).ravel()
        if vec.size >= 2:
            return { 'arousal': float(vec[0]), 'valence': float(vec[1]) }
        elif vec.size == 1:
            return { 'arousal': float(vec[0]), 'valence': None }                
        return None

    head_pb_v = _first_existing([
        os.path.join(VA_DIR, 'deam-audioset-vggish-2.pb'),
        os.path.join(VA_DIR, 'deam-audioset-vggish-1.pb'),
    ])
    vgg = _load_vggish() if head_pb_v else None
    if vgg and head_pb_v:
        try:
            res = _run_with_head(head_pb_v, vgg)
            if res:
                return { 'model_name': 'deam-audioset-vggish', **res }
        except Exception as e:
            print('[musicnn_models] valence/arousal VGGish error:', str(e))
            return None
    return None

def predict_mood_mirex(filename: str) -> Optional[Dict]:
    """Use MusiCNN backbone + Mood MIREX 5-class head.

    Returns {'model_name': 'moods_mirex-msd-musicnn-1', 'top': str, 'candidates': [(label, score), ...]}
    """
    if es is None:
        return None
    head_pb = _first_existing([
        os.path.join(MIREX_DIR, 'moods_mirex-msd-musicnn-1.pb'),
    ])
    head_json = _first_existing([
        os.path.join(MIREX_DIR, 'moods_mirex-msd-musicnn-1.json'),
    ])
    use_vggish = False
    musicnn = None

    def _run_with_head(_head_pb: str, _head_json: Optional[str], embedder):
        print(f"[mirex] using head: {_head_pb}")
        x = _prepare_audio_16k(filename)
        emb = embedder(x)
        emb_np = np.asarray(emb)
        if emb_np.ndim == 1:
            emb_np = emb_np.reshape(1, -1)
        io_candidates = [
            ("serving_default_model_Placeholder", "StatefulPartitionedCall"),
            ("serving_default_model_Placeholder", "StatefulPartitionedCall:0"),
            ("serving_default_model_Placeholder", "StatefulPartitionedCall_1"),
            ("serving_default_model_Placeholder", "StatefulPartitionedCall_1:0"),
        ]
        out = None
        last = None
        for inp, outn in io_candidates:
            try:
                clf = es.TensorflowPredict2D(graphFilename=_head_pb, input=inp, output=outn)
                out = clf(emb_np)
                print(f"[mirex] matched io nodes: input='{inp}', output='{outn}'")
                break
            except Exception as e:
                if last is None:
                    print(f"[mirex] io pair failed (input='{inp}', output='{outn}') -> {e}")
                last = e
                continue
        if out is None:
            raise last or RuntimeError('Cannot run MIREX head')
        vec = np.asarray(out)
        if vec.ndim == 2:
            vec = vec.mean(axis=0)
        vec = np.asarray(vec).ravel()
        labels: List[str] = []
        if _head_json and os.path.exists(_head_json):
            try:
                import json as _json
                with open(_head_json, 'r', encoding='utf-8') as f:
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
        return top, pairs

    head_pb_v = _first_existing([
        os.path.join(MIREX_DIR, 'moods_mirex-audioset-vggish-1.pb'),
        os.path.join(MIREX_DIR, 'moods_mirex-vggish-audioset-1.pb'),
    ])
    head_json_v = _first_existing([
        os.path.join(MIREX_DIR, 'moods_mirex-audioset-vggish-1.json'),
        os.path.join(MIREX_DIR, 'moods_mirex-vggish-audioset-1.json'),
    ])
    if not head_pb_v:
        return None
    vgg = _load_vggish()
    if vgg is None:
        return None
    try:
        top, pairs = _run_with_head(head_pb_v, head_json_v, vgg)
        return {'model_name': 'moods_mirex-audioset-vggish-1', 'top': top, 'candidates': pairs}
    except Exception as e:
        print('[musicnn_models] MIREX VGGish error:', str(e))
        return None
