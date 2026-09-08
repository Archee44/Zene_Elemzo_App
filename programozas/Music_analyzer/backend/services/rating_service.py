from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.models import AudioFeatures, Song
from backend.models.user import InteractionTypeEnum, UserInteraction, UserProfile
from backend.services.faiss_recommender import (
    _ensure_index,
    _impute_feature_tuple,
    _vector_from_values,
    _clamp,
    _STATE,
    _FEATURE_NAMES,
)

RATING_TYPES = {
    "like": InteractionTypeEnum.like,
    "dislike": InteractionTypeEnum.dislike,
}


def _find_rating(db: Session, user_id: int, song_id: int) -> Optional[UserInteraction]:
    return (
        db.query(UserInteraction)
        .filter(
            UserInteraction.user_id == user_id,
            UserInteraction.song_id == song_id,
            UserInteraction.interaction_type.in_([InteractionTypeEnum.like, InteractionTypeEnum.dislike]),
        )
        .first()
    )


def set_rating(user_id: int, song_id: int, rating: str, db: Session) -> UserInteraction:
    interaction_type = RATING_TYPES[rating]

    existing = _find_rating(db, user_id, song_id)
    if existing:
        existing.interaction_type = interaction_type
        existing.timestamp = datetime.now(timezone.utc)
    else:
        existing = UserInteraction(user_id=user_id, song_id=song_id, interaction_type=interaction_type)
        db.add(existing)

    db.commit()
    db.refresh(existing)
    recompute_profile_vector(user_id, db)
    return existing


def remove_rating(user_id: int, song_id: int, db: Session) -> bool:
    existing = _find_rating(db, user_id, song_id)
    if not existing:
        return False
    db.delete(existing)
    db.commit()
    recompute_profile_vector(user_id, db)
    return True


def _liked_song_ids(db: Session, user_id: int) -> List[int]:
    rows = (
        db.query(UserInteraction.song_id)
        .filter(UserInteraction.user_id == user_id, UserInteraction.interaction_type == InteractionTypeEnum.like)
        .all()
    )
    return [r[0] for r in rows]


def recompute_profile_vector(user_id: int, db: Session) -> Optional[List[float]]:
    liked_ids = _liked_song_ids(db, user_id)

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    if not liked_ids:
        profile.profile_vector = None
        profile.last_updated = datetime.now(timezone.utc)
        db.commit()
        return None

    _ensure_index(db)

    rows = (
        db.query(
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
        .filter(Song.id.in_(liked_ids))
        .all()
    )
    if not rows:
        profile.profile_vector = None
        profile.last_updated = datetime.now(timezone.utc)
        db.commit()
        return None

    global_medians = _STATE.global_medians or {name: 0.0 for name in _FEATURE_NAMES}
    family_medians = _STATE.family_medians or {}

    vectors = []
    for row in rows:
        genre_family, *values = row
        filled = _impute_feature_tuple(genre_family, values, global_medians, family_medians)
        vectors.append(_vector_from_values(*filled))

    avg = np.mean(np.vstack(vectors), axis=0)
    norm = float(np.linalg.norm(avg))
    if norm > 1e-12:
        avg = avg / norm

    profile.profile_vector = [float(x) for x in avg]
    profile.last_updated = datetime.now(timezone.utc)
    db.commit()
    return profile.profile_vector


def get_favorites(user_id: int, db: Session) -> Dict[str, List[dict]]:
    rows = (
        db.query(UserInteraction.interaction_type, Song.id, Song.title, Song.artist_name, Song.genre, Song.genre_family)
        .join(Song, Song.id == UserInteraction.song_id)
        .filter(
            UserInteraction.user_id == user_id,
            UserInteraction.interaction_type.in_([InteractionTypeEnum.like, InteractionTypeEnum.dislike]),
        )
        .all()
    )
    liked, disliked = [], []
    for interaction_type, song_id, title, artist_name, genre, genre_family in rows:
        item = {"id": song_id, "title": title, "artist": artist_name, "genre": genre, "genre_family": genre_family}
        (liked if interaction_type == InteractionTypeEnum.like else disliked).append(item)
    return {"liked": liked, "disliked": disliked}


def get_taste_summary(user_id: int, db: Session) -> dict:
    liked_ids = _liked_song_ids(db, user_id)
    if not liked_ids:
        return {"genres": [], "features": None, "liked_count": 0}

    genre_rows = db.query(Song.genre_family).filter(Song.id.in_(liked_ids)).all()
    counts = Counter((g or "Ismeretlen").strip().title() for (g,) in genre_rows if g)
    total = sum(counts.values()) or 1
    top_genres = [
        {"label": label, "value": round(count / total * 100, 1)}
        for label, count in counts.most_common(5)
    ]

    feature_rows = (
        db.query(
            AudioFeatures.energy,
            AudioFeatures.danceability,
            AudioFeatures.valence,
            AudioFeatures.acousticness,
        )
        .filter(AudioFeatures.song_id.in_(liked_ids))
        .all()
    )
    sums = {"energy": 0.0, "danceability": 0.0, "valence": 0.0, "acousticness": 0.0}
    counted = {"energy": 0, "danceability": 0, "valence": 0, "acousticness": 0}
    for energy, danceability, valence, acousticness in feature_rows:
        for name, value in (
            ("energy", energy),
            ("danceability", danceability),
            ("valence", valence),
            ("acousticness", acousticness),
        ):
            if value is not None:
                sums[name] += _clamp(value, 0.0, 1.0)
                counted[name] += 1

    features = {
        name: round(sums[name] / counted[name], 3) if counted[name] else None
        for name in sums
    }

    return {"genres": top_genres, "features": features, "liked_count": len(liked_ids)}
