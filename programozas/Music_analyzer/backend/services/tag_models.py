from __future__ import annotations

import os
import json
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import essentia
    import essentia.standard as es
except ImportError:
    es = None

from backend.services.audio_loader import load_mono
from backend.services.log_filter import run_quietly

MODEL_DIR = os.getenv("ESSENTIA_MODEL_DIR", "/app/models")
DISCOGS_DIR = os.path.join(MODEL_DIR, "discogs400")
BRIGHT_DARK_DIR = os.path.join(MODEL_DIR, "bright_dark")
VOICE_INST_DIR = os.path.join(MODEL_DIR, "instrumental_voice")
MOOD_ACOUSTIC_DIR = os.path.join(MODEL_DIR, "mood_acoustic")

_EFFNET_PRED = None
_HEAD_CACHE: Dict[str, es.TensorflowPredict2D] = {} if es else {}

def _first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

def _find_head_file(directory: str, token: str) -> Optional[str]:
    """Pick the first .pb that contains the token in its filename."""
    try:
        for name in os.listdir(directory):
            low = name.lower()
            if not low.endswith(".pb"):
                continue
            if token.lower() in low:
                return os.path.join(directory, name)
    except Exception:
        return None
    return None

def _matching_json(pb_path: Optional[str]) -> Optional[str]:
    if not pb_path:
        return None
    base = os.path.splitext(os.path.basename(pb_path))[0]
    root = os.path.dirname(pb_path)
    cand = os.path.join(root, base + ".json")
    if os.path.exists(cand):
        return cand
    try:
        for name in os.listdir(root):
            if name.lower().endswith(".json"):
                return os.path.join(root, name)
    except Exception:
        pass
    return None

def _load_effnet() -> Optional[es.TensorflowPredictEffnetDiscogs]:
    effnet_candidates = [
        os.path.join(DISCOGS_DIR, "discogs-effnet-bs64-1.pb"),
        os.path.join(DISCOGS_DIR, "discogs-effnet-bs64.pb"),
    ]
    effnet_pb = _first_existing(effnet_candidates)
    if not effnet_pb:
        return None
    global _EFFNET_PRED
    if _EFFNET_PRED is None:
        _EFFNET_PRED = es.TensorflowPredictEffnetDiscogs(
            graphFilename=effnet_pb,
            output="PartitionedCall:1",
        )
    return _EFFNET_PRED

def _prepare_audio(filename: str) -> np.ndarray:
    audio = load_mono(filename, sample_rate=16000)
    if isinstance(audio, (list, tuple)):
        audio = np.asarray(audio)
    max_len = 60 * 16000
    if audio.shape[0] > max_len:
        audio = audio[:max_len]
    return audio.astype(np.float32)

def _run_effnet_head(
    filename: str,
    head_dir: str,
    token: str,
    default_labels: List[str],
    model_name: Optional[str] = None,
) -> Optional[Dict]:
    if es is None:
        return None
    if not os.path.isdir(head_dir):
        return None

    head_pb = _find_head_file(head_dir, token)
    if not head_pb:
        return None
    head_json = _matching_json(head_pb)

    try:
        audio = _prepare_audio(filename)
        effnet = _load_effnet()
        if effnet is None:
            return None
        emb = run_quietly(effnet, audio)
        emb_np = np.asarray(emb)
        if emb_np.ndim == 1:
            emb_np = emb_np.reshape(1, -1)

        io_candidates: List[Tuple[str, str]] = [
            ("serving_default_model_Placeholder", "PartitionedCall:0"),
            ("model/Placeholder", "model/Softmax"),
            ("Placeholder", "model/Softmax"),
            ("model/Placeholder", "Identity"),
            ("serving_default_model_Placeholder", "Identity:0"),
            ("Placeholder", "Identity"),
            ("serving_default_input", "StatefulPartitionedCall:0"),
            ("serving_default_input_1", "StatefulPartitionedCall:0"),
        ]

        out = None
        last_err = None
        clf = _HEAD_CACHE.get(head_pb)
        if clf is not None:
            try:
                out = run_quietly(clf, emb_np)
            except Exception:
                clf = None
        if clf is None:
            for inp_name, out_name in io_candidates:
                try:
                    clf = es.TensorflowPredict2D(
                        graphFilename=head_pb,
                        input=inp_name,
                        output=out_name,
                    )
                    out = run_quietly(clf, emb_np)
                    _HEAD_CACHE[head_pb] = clf
                    break
                except Exception as e:
                    last_err = e
                    continue
        if out is None:
            raise last_err or RuntimeError("No valid IO nodes for head")

        out_np = np.asarray(out)
        if out_np.ndim == 2:
            out_vec = out_np.mean(axis=0)
        else:
            out_vec = out_np
        out_vec = np.asarray(out_vec).ravel()

        labels: List[str] = []
        if head_json and os.path.exists(head_json):
            try:
                with open(head_json, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                labels = [str(c) for c in (meta.get("classes") or [])]
            except Exception:
                labels = []
        if not labels:
            labels = list(default_labels) if default_labels else [f"class_{i}" for i in range(out_vec.size)]

        L = min(len(labels), out_vec.size)
        pairs = [(labels[i], float(out_vec[i])) for i in range(L)]
        pairs.sort(key=lambda x: x[1], reverse=True)
        top = pairs[0][0] if pairs else None
        return {
            "model_name": model_name or os.path.splitext(os.path.basename(head_pb))[0],
            "top": top,
            "candidates": pairs,
        }
    except Exception as e:
        print(f"[tag_models] inference error for token='{token}':", str(e))
        return None

def predict_bright_dark(filename: str) -> Optional[Dict]:
    return _run_effnet_head(
        filename,
        BRIGHT_DARK_DIR,
        "bright_dark",
        ["bright", "dark"],
        model_name="bright_dark-discogs-effnet",
    )

def predict_voice_instrumental(filename: str) -> Optional[Dict]:
    return _run_effnet_head(
        filename,
        VOICE_INST_DIR,
        "voice_instrumental",
        ["instrumental", "voice"],
        model_name="voice_instrumental-discogs-effnet",
    )

def predict_mood_acoustic(filename: str) -> Optional[Dict]:
    return _run_effnet_head(
        filename,
        MOOD_ACOUSTIC_DIR,
        "mood_acoustic",
        ["acoustic", "non_acoustic"],
        model_name="mood_acoustic-discogs-effnet",
    )
