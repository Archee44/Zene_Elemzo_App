from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy.orm import Session

from backend.models import AudioFeatures, Song

try:
    import faiss                
except Exception:
    faiss = None

FEATURE_DIM = 8

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

def _vector_from_values(
    tempo: Optional[float],
    energy: Optional[float],
    danceability: Optional[float],
    valence: Optional[float],
    acousticness: Optional[float],
    loudness: Optional[float],
    spectral_centroid: Optional[float],
    spectral_bandwidth: Optional[float],
) -> np.ndarray:
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
    n = float(np.linalg.norm(vec))
    if n > 1e-12:
        vec /= n
    return vec

@dataclass
class _FaissState:
    index: Optional["faiss.IndexFlatIP"] = None
    song_ids: Optional[np.ndarray] = None
    indexed_rows: int = 0
    dirty: bool = True
    global_medians: Optional[Dict[str, float]] = None
    family_medians: Optional[Dict[str, Dict[str, float]]] = None

_STATE = _FaissState()
_LOCK = Lock()
_FEATURE_NAMES = [
    "tempo",
    "energy",
    "danceability",
    "valence",
    "acousticness",
    "loudness",
    "spectral_centroid",
    "spectral_bandwidth",
]

def _confidence_score(value: Optional[str]) -> float:
    label = (value or "").strip().lower()
    if label == "high":
        return 8.0
    if label == "medium":
        return 2.0
    if label == "low":
        return -10.0
    return -2.0

def _variant_penalty(value: Optional[int]) -> float:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0.0
    if count <= 1:
        return 0.0
    if count == 2:
        return -1.5
    if count == 3:
        return -3.0
    return -5.0 - min(8.0, float(count - 4))

def _raw_genre_set(value: Optional[str]) -> set[str]:
    if not value:
        return set()
    return {
        part.strip().lower()
        for part in str(value).split("|")
        if part and part.strip()
    }

def _raw_genre_overlap_score(
    seed_raw: set[str],
    candidate_raw: set[str],
    seed_confidence: Optional[str],
    candidate_confidence: Optional[str],
) -> float:
    if not seed_raw or not candidate_raw:
        return 0.0
    overlap = seed_raw.intersection(candidate_raw)
    if not overlap:
        return 0.0
    scale = min(1.0, len(overlap) / max(len(seed_raw), 1))
    base = 14.0 * scale
    low_confidence_count = sum(
        1
        for label in ((seed_confidence or "").strip().lower(), (candidate_confidence or "").strip().lower())
        if label == "low"
    )
    if low_confidence_count == 2:
        base *= 0.45
    elif low_confidence_count == 1:
        base *= 0.7
    return base

def is_available() -> bool:
    return faiss is not None

def mark_index_dirty() -> None:
    with _LOCK:
        _STATE.dirty = True

def _load_feature_rows(db: Session) -> List[Tuple[int, Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]]:
    return (
        db.query(
            Song.id,
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
    rows: List[Tuple[int, Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]],
    db: Session,
) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    song_ids = [r[0] for r in rows]
    families = dict(
        db.query(Song.id, Song.genre_family)
        .filter(Song.id.in_(song_ids))
        .all()
    )

    global_values: Dict[str, List[float]] = {name: [] for name in _FEATURE_NAMES}
    family_values: Dict[str, Dict[str, List[float]]] = {}

    for row in rows:
        song_id = row[0]
        family = (families.get(song_id) or "").strip().lower()
        values = row[1:]
        for name, value in zip(_FEATURE_NAMES, values):
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

def _impute_feature_tuple(
    genre_family: Optional[str],
    values: Sequence[Optional[float]],
    global_medians: Dict[str, float],
    family_medians: Dict[str, Dict[str, float]],
) -> Tuple[float, ...]:
    family_key = (genre_family or "").strip().lower()
    family_stats = family_medians.get(family_key, {})
    out: List[float] = []
    for name, value in zip(_FEATURE_NAMES, values):
        if value is None:
            out.append(family_stats.get(name, global_medians[name]))
        else:
            out.append(float(value))
    return tuple(out)

def rebuild_index(db: Session) -> Dict[str, int | bool]:
    if faiss is None:
        return {"available": False, "indexed_rows": 0}

    rows = _load_feature_rows(db)
    if not rows:
        with _LOCK:
            _STATE.index = None
            _STATE.song_ids = None
            _STATE.indexed_rows = 0
            _STATE.dirty = False
        return {"available": True, "indexed_rows": 0}

    global_medians, family_medians = _compute_medians(rows, db)
    song_families = dict(
        db.query(Song.id, Song.genre_family)
        .filter(Song.id.in_([r[0] for r in rows]))
        .all()
    )

    song_ids = np.array([r[0] for r in rows], dtype=np.int64)
    vectors = np.zeros((len(rows), FEATURE_DIM), dtype=np.float32)

    for i, r in enumerate(rows):
        filled = _impute_feature_tuple(
            song_families.get(r[0]),
            r[1:],
            global_medians,
            family_medians,
        )
        vectors[i] = _vector_from_values(
            filled[0],
            filled[1],
            filled[2],
            filled[3],
            filled[4],
            filled[5],
            filled[6],
            filled[7],
        )

    idx = faiss.IndexFlatIP(FEATURE_DIM)
    idx.add(vectors)

    with _LOCK:
        _STATE.index = idx
        _STATE.song_ids = song_ids
        _STATE.indexed_rows = int(len(rows))
        _STATE.dirty = False
        _STATE.global_medians = global_medians
        _STATE.family_medians = family_medians

    return {"available": True, "indexed_rows": int(len(rows))}

def _ensure_index(db: Session) -> bool:
    if faiss is None:
        return False
    needs_rebuild = False
    with _LOCK:
        if _STATE.index is None or _STATE.dirty:
            needs_rebuild = True
    if needs_rebuild:
        rebuild_index(db)
    with _LOCK:
        return _STATE.index is not None and _STATE.song_ids is not None

def recommend_by_song_id(song_id: int, db: Session, limit: int = 5) -> Optional[List[Dict]]:
    if not _ensure_index(db):
        return None

    row = (
        db.query(
            Song.genre,
            Song.genre_family,
            Song.raw_genres,
            Song.genre_confidence,
            Song.genre_variant_count,
            Song.cluster_id,
            AudioFeatures.tempo,
            AudioFeatures.energy,
            AudioFeatures.danceability,
            AudioFeatures.valence,
            AudioFeatures.acousticness,
            AudioFeatures.loudness,
            AudioFeatures.spectral_centroid,
            AudioFeatures.spectral_bandwidth,
        )
        .join(Song, Song.id == AudioFeatures.song_id)
        .filter(AudioFeatures.song_id == song_id)
        .first()
    )
    if row is None:
        return []

    seed_genre = (row[0] or "").strip().lower()
    seed_genre_family = (row[1] or "").strip().lower()
    seed_raw_genres = _raw_genre_set(row[2])
    seed_confidence = (row[3] or "").strip().lower()
    seed_variant_count = row[4]
    seed_cluster_id = row[5]
    with _LOCK:
        global_medians = _STATE.global_medians or {name: 0.0 for name in _FEATURE_NAMES}
        family_medians = _STATE.family_medians or {}
    filled = _impute_feature_tuple(
        row[1],
        row[6:],
        global_medians,
        family_medians,
    )
    q = _vector_from_values(
        filled[0],
        filled[1],
        filled[2],
        filled[3],
        filled[4],
        filled[5],
        filled[6],
        filled[7],
    ).reshape(1, -1)

    with _LOCK:
        idx = _STATE.index
        song_ids = _STATE.song_ids
        if idx is None or song_ids is None:
            return None
        # Genre/cluster reranking below only ever sees whatever comes back from this
        # raw vector search, so with a genre-imbalanced catalog (a handful of songs
        # per genre out of thousands) a narrow top-k can miss every matching-genre
        # candidate. Cast a much wider net and let the reranking narrow it down.
        k = min(int(song_ids.shape[0]), max(limit * 50, 300))
        distances, neighbors = idx.search(q, k)

    candidate_ids: List[int] = []
    vector_scores: Dict[int, float] = {}
    for pos, score in zip(neighbors[0], distances[0]):
        if pos < 0:
            continue
        sid = int(song_ids[pos])
        if sid == song_id or sid in vector_scores:
            continue
        vector_scores[sid] = float(score)
        candidate_ids.append(sid)

    if not candidate_ids:
        return []

    songs = (
        db.query(
            Song.id,
            Song.title,
            Song.artist_name,
            Song.genre,
            Song.genre_family,
            Song.raw_genres,
            Song.genre_confidence,
            Song.genre_variant_count,
            Song.cluster_id,
        )
        .filter(Song.id.in_(candidate_ids))
        .all()
    )
    meta = {
        s.id: {
            "id": s.id,
            "title": s.title,
            "artist": s.artist_name,
            "genre": s.genre,
            "genre_family": s.genre_family,
            "raw_genres": s.raw_genres,
            "genre_confidence": s.genre_confidence,
            "genre_variant_count": s.genre_variant_count,
            "cluster_id": s.cluster_id,
        }
        for s in songs
    }

    ranked: List[Tuple[float, int]] = []
    for sid in candidate_ids:
        item = meta.get(sid)
        if item is None:
            continue
        final_score = vector_scores[sid] * 100.0
        cand_genre = (item.get("genre") or "").strip().lower()
        cand_genre_family = (item.get("genre_family") or "").strip().lower()
        cand_raw_genres = _raw_genre_set(item.get("raw_genres"))
        cand_confidence = item.get("genre_confidence")
        cand_variant_count = item.get("genre_variant_count")
        cand_cluster_id = item.get("cluster_id")
        final_score += _confidence_score(cand_confidence)
        final_score += _variant_penalty(cand_variant_count)
        final_score += _raw_genre_overlap_score(
            seed_raw_genres,
            cand_raw_genres,
            seed_confidence,
            cand_confidence,
        )
        if seed_genre and cand_genre:
            exact_bonus = 35.0 if seed_confidence == "high" else 24.0 if seed_confidence == "medium" else 14.0
            fuzzy_bonus = 20.0 if seed_confidence == "high" else 12.0 if seed_confidence == "medium" else 7.0
            if cand_genre == seed_genre:
                final_score += exact_bonus
            elif cand_genre.replace("-", " ") == seed_genre.replace("-", " "):
                final_score += fuzzy_bonus
        if seed_genre_family and cand_genre_family:
            same_family_bonus = 12.0 if seed_confidence != "low" else 6.0
            different_family_penalty = -18.0 if seed_confidence == "high" else -12.0 if seed_confidence == "medium" else -6.0
            if cand_genre_family == seed_genre_family:
                final_score += same_family_bonus
            else:
                final_score += different_family_penalty
        if seed_cluster_id is not None and cand_cluster_id is not None:
            if cand_cluster_id == seed_cluster_id:
                final_score += 25.0
            else:
                final_score -= 10.0
        final_score += _variant_penalty(seed_variant_count) * 0.5
        ranked.append((final_score, sid))

    ranked.sort(key=lambda x: x[0], reverse=True)

    same_cluster: List[Tuple[float, int]] = []
    other_cluster: List[Tuple[float, int]] = []
    for pair in ranked:
        sid = pair[1]
        item = meta.get(sid)
        if item is None:
            continue
        if seed_cluster_id is not None and item.get("cluster_id") == seed_cluster_id:
            same_cluster.append(pair)
        else:
            other_cluster.append(pair)

    selected = same_cluster[:limit]
    if len(selected) < limit:
        selected.extend(other_cluster[: max(0, limit - len(selected))])

    out: List[Dict] = []
    for final_score, sid in selected:
        item = meta.get(sid)
        if item is None:
            continue
        item["score"] = round(final_score, 4)
        out.append(item)
    return out
