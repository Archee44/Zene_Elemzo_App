from __future__ import annotations

from math import sqrt
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy.orm import Session

from backend.models import AudioFeatures, Song

try:
    from sklearn.cluster import MiniBatchKMeans
except Exception:
    MiniBatchKMeans = None

FEATURE_NAMES = [
    "tempo",
    "energy",
    "danceability",
    "valence",
    "acousticness",
    "loudness",
    "spectral_centroid",
    "spectral_bandwidth",
]

def is_available() -> bool:
    return MiniBatchKMeans is not None

def _clamp(v: Optional[float], lo: float, hi: float, default: float = 0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x

def _vector_from_values(values: Sequence[float]) -> np.ndarray:
    tempo, energy, danceability, valence, acousticness, loudness, spectral_centroid, spectral_bandwidth = values
    vec = np.array(
        [
            _clamp(tempo, 0.0, 250.0) / 250.0,
            _clamp(energy, 0.0, 1.0),
            _clamp(danceability, 0.0, 1.0),
            _clamp(valence, 0.0, 1.0),
            _clamp(acousticness, 0.0, 1.0),
            (_clamp(loudness, -60.0, 2.0) + 60.0) / 62.0,
            _clamp(spectral_centroid, 0.0, 8000.0) / 8000.0,
            _clamp(spectral_bandwidth, 0.0, 4000.0) / 4000.0,
        ],
        dtype=np.float32,
    )
    return vec

def _load_rows(db: Session) -> List[Tuple[int, Optional[str], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]]:
    return (
        db.query(
            Song.id,
            Song.genre_family,
            AudioFeatures.tempo,
            AudioFeatures.energy,
            AudioFeatures.danceability,
            AudioFeatures.valence,
            AudioFeatures.acousticness,
            AudioFeatures.loudness,
            AudioFeatures.spectral_centroid,
            AudioFeatures.spectral_bandwidth,
        )
        .join(AudioFeatures, AudioFeatures.song_id == Song.id)
        .all()
    )

def _compute_medians(
    rows: List[Tuple[int, Optional[str], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]]
) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    global_values: Dict[str, List[float]] = {name: [] for name in FEATURE_NAMES}
    family_values: Dict[str, Dict[str, List[float]]] = {}

    for row in rows:
        family = (row[1] or "").strip().lower()
        for name, value in zip(FEATURE_NAMES, row[2:]):
            if value is None:
                continue
            fv = float(value)
            global_values[name].append(fv)
            if family:
                family_values.setdefault(family, {}).setdefault(name, []).append(fv)

    global_medians = {
        name: float(np.median(vals)) if vals else 0.0
        for name, vals in global_values.items()
    }
    family_medians: Dict[str, Dict[str, float]] = {}
    for family, feature_map in family_values.items():
        family_medians[family] = {
            name: float(np.median(vals)) if vals else global_medians[name]
            for name, vals in feature_map.items()
        }
    return global_medians, family_medians

def _impute_row(
    family: Optional[str],
    values: Sequence[Optional[float]],
    global_medians: Dict[str, float],
    family_medians: Dict[str, Dict[str, float]],
) -> Tuple[float, ...]:
    family_key = (family or "").strip().lower()
    family_stats = family_medians.get(family_key, {})
    out: List[float] = []
    for name, value in zip(FEATURE_NAMES, values):
        if value is None:
            out.append(family_stats.get(name, global_medians[name]))
        else:
            out.append(float(value))
    return tuple(out)

def _choose_cluster_count(n_rows: int) -> int:
    if n_rows < 20:
        return 1
    return max(8, min(128, int(sqrt(n_rows / 2.0))))

def rebuild_clusters(db: Session) -> Dict[str, int | bool]:
    if MiniBatchKMeans is None:
        return {"available": False, "cluster_count": 0, "clustered_rows": 0}

    rows = _load_rows(db)
    if not rows:
        return {"available": True, "cluster_count": 0, "clustered_rows": 0}

    global_medians, family_medians = _compute_medians(rows)
    vectors = np.zeros((len(rows), len(FEATURE_NAMES)), dtype=np.float32)
    song_ids: List[int] = []
    for idx, row in enumerate(rows):
        song_ids.append(int(row[0]))
        filled = _impute_row(row[1], row[2:], global_medians, family_medians)
        vectors[idx] = _vector_from_values(filled)

    cluster_count = _choose_cluster_count(len(rows))
    if cluster_count <= 1:
        labels = np.zeros(len(rows), dtype=np.int32)
    else:
        model = MiniBatchKMeans(
            n_clusters=cluster_count,
            random_state=42,
            batch_size=min(4096, max(512, len(rows))),
            n_init=10,
        )
        labels = model.fit_predict(vectors)

    for song_id, cluster_id in zip(song_ids, labels.tolist()):
        db.query(Song).filter(Song.id == song_id).update(
            {"cluster_id": int(cluster_id)},
            synchronize_session=False,
        )
    db.commit()

    return {
        "available": True,
        "cluster_count": int(len(set(labels.tolist()))),
        "clustered_rows": int(len(song_ids)),
    }
