from __future__ import annotations

import os
from typing import Dict, List, Tuple, Optional
import numpy as np

try:
    import essentia
    import essentia.standard as es
except ImportError:
    es = None
from backend.services.log_filter import run_quietly
from backend.services.audio_loader import load_mono

MACRO_MAP = {
    "pop": "Pop",
    "dance pop": "Pop",
    "electropop": "Pop",
    "synthpop": "Pop",
    "k-pop": "Pop",
    "pop rock": "Pop",

    "rock": "Rock",
    "hard rock": "Rock",
    "alternative rock": "Rock",
    "indie rock": "Rock",
    "punk": "Rock",
    "metal": "Metal",
    "heavy metal": "Metal",
    "death metal": "Metal",

    "hip hop": "Hip-Hop/Rap",
    "rap": "Hip-Hop/Rap",
    "trap": "Hip-Hop/Rap",
    "boom bap": "Hip-Hop/Rap",

    "edm": "Dance/Electronic",
    "house": "Dance/Electronic",
    "deep house": "Dance/Electronic",
    "techno": "Dance/Electronic",
    "trance": "Dance/Electronic",
    "drum and bass": "Dance/Electronic",
    "dubstep": "Dance/Electronic",
    "electronic": "Dance/Electronic",

    "r&b": "R&B/Soul",
    "soul": "R&B/Soul",
    "neo soul": "R&B/Soul",

    "reggaeton": "Latin/Reggaeton",
    "latin": "Latin/Reggaeton",
    "salsa": "Latin/Reggaeton",
    "bachata": "Latin/Reggaeton",

    "acoustic": "Acoustic/Folk",
    "folk": "Acoustic/Folk",
    "singer-songwriter": "Acoustic/Folk",

    "jazz": "Jazz/Blues",
    "blues": "Jazz/Blues",

    "classical": "Classical/Orchestral",
    "orchestral": "Classical/Orchestral",
}

MODEL_DIR = os.getenv('ESSENTIA_MODEL_DIR', '/app/models')
DISCOGS_DIR = os.path.join(MODEL_DIR, 'discogs400')
EFFNET_CANDIDATES = [
    os.path.join(DISCOGS_DIR, 'discogs-effnet-bs64-1.pb'),
    os.path.join(DISCOGS_DIR, 'discogs-effnet-bs64.pb'),
]
GENRE_CANDIDATES = [
    os.path.join(DISCOGS_DIR, 'genre_discogs400-discogs-effnet-1.pb'),
    os.path.join(DISCOGS_DIR, 'genre_discogs400-effnet-1.pb'),
]
LABELS_CANDIDATES = [
    os.path.join(DISCOGS_DIR, 'genre_discogs400_labels.txt'),
    os.path.join(DISCOGS_DIR, 'genre_discogs400.labels.txt'),
]
LABELS_JSON_CANDIDATES = [
    os.path.join(DISCOGS_DIR, 'genre_discogs400-discogs-effnet-1.json'),
]

def _read_labels_any() -> List[str]:
    for p in LABELS_CANDIDATES:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    return [line.strip() for line in f if line.strip()]
            except Exception:
                pass
    for p in LABELS_JSON_CANDIDATES:
        if os.path.exists(p):
            try:
                import json as _json
                with open(p, 'r', encoding='utf-8') as f:
                    meta = _json.load(f)
                classes = meta.get('classes') or []
                return [str(c) for c in classes]
            except Exception:
                pass
    return []

def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None

_EFFNET_PRED = None
_GENRE_CLF_CACHE = {}

def infer_with_discogs400(filename: str) -> Optional[Dict]:
    if es is None:
        print("[genre_model] Essentia not available; cannot run Discogs400")
        return None
    effnet_pb = _first_existing(EFFNET_CANDIDATES)
    genre_pb = _first_existing(GENRE_CANDIDATES)
    labels_txt = _first_existing(LABELS_CANDIDATES)
    labels_json = _first_existing(LABELS_JSON_CANDIDATES)
    if not (effnet_pb and genre_pb and (labels_txt or labels_json)):
        print("[genre_model] Missing model files:", {
            'effnet': effnet_pb or 'NOT FOUND',
            'genre': genre_pb or 'NOT FOUND',
            'labels_txt': labels_txt or 'NOT FOUND',
            'labels_json': labels_json or 'NOT FOUND',
        })
        return None
    try:
        audio = load_mono(filename, sample_rate=16000)
        if isinstance(audio, (list, tuple)):
            import numpy as _np
            audio = _np.asarray(audio)
        try:
            max_len = 60 * 16000
            if len(audio) > max_len:
                audio = audio[:max_len]
        except Exception:
            pass
        global _EFFNET_PRED
        if _EFFNET_PRED is None:
            _EFFNET_PRED = es.TensorflowPredictEffnetDiscogs(
                graphFilename=effnet_pb,
                output="PartitionedCall:1"
            )
        embeddings = run_quietly(_EFFNET_PRED, audio)
        emb_np = np.asarray(embeddings)
        if emb_np.ndim == 1:
            emb_np = emb_np.reshape(1, -1)
        clf = _GENRE_CLF_CACHE.get(genre_pb)
        if clf is None:
            clf = es.TensorflowPredict2D(
                graphFilename=genre_pb,
                input="serving_default_model_Placeholder",
                output="PartitionedCall:0"
            )
            _GENRE_CLF_CACHE[genre_pb] = clf
        preds = run_quietly(clf, emb_np)
        preds_np = np.asarray(preds)
        if preds_np.ndim == 2:
            preds_vec = preds_np.mean(axis=0)
        else:
            preds_vec = preds_np
        preds_vec = np.asarray(preds_vec).ravel()
        labels = _read_labels_any()
        if not labels:
            return None
        L = min(len(labels), preds_vec.size)
        pairs = [(labels[i], float(preds_vec[i])) for i in range(L)]
        pairs.sort(key=lambda x: float(x[1]), reverse=True)
        top_label, top_score = pairs[0]
        return {
            'model_name': 'discogs400-effnet',
            'top': top_label,
            'candidates': pairs,
        }
    except Exception as e:
        print("[genre_model] Discogs400 inference error:", str(e))
        return None

def macro_from_candidates(cands: List[Tuple[str, float]]) -> Optional[str]:
    if not cands:
        return None
    for label, _ in cands:
        key = label.lower()
        if key in MACRO_MAP:
            return MACRO_MAP[key]
        for k, macro in MACRO_MAP.items():
            if k in key:
                return macro
    return None

def predict_genres(filename: str) -> Dict:
    """Main entry: returns model-based genre predictions if possible.

    It tries MusicExtractor first. Structure:
      {
        'genre_model': str | None,
        'genre_model_candidates': [{'label': str, 'score': float}, ...],
        'genre_model_macro': str | None,
        'genre_model_name': str | None,
      }
    """
    out: Dict = {
        'genre_model': None,
        'genre_model_candidates': [],
        'genre_model_macro': None,
        'genre_model_name': None,
    }

    res = infer_with_discogs400(filename)
    if res:
        out['genre_model_name'] = res.get('model_name')
        out['genre_model'] = res.get('top')
        cands = res.get('candidates') or []
        out['genre_model_candidates'] = [
            {'label': l, 'score': float(s)} for l, s in cands
        ]
        out['genre_model_macro'] = macro_from_candidates(cands)

    return out
