import os
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models import Song, AudioFeatures, SourceTypeEnum
from backend.services.music_analyze import analyze_music
from backend.services.faiss_recommender import (
    recommend_by_song_id,
    mark_index_dirty,
)
from backend.services.genre_taxonomy import genre_family_for

def _pick_best_genre(analysis_result: dict) -> Optional[str]:
    candidates = [
        analysis_result.get("genre_model"),
        analysis_result.get("genre_detailed"),
        analysis_result.get("genre"),
        analysis_result.get("genre_model_macro"),
    ]
    for value in candidates:
        if not value:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"unknown", "unknown genre"}:
            return text
    return None

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

def get_or_create_song_from_file(file_path: str, db: Session) -> Song:
    """
    Analyzes a music file using the main Essentia service, checks if the song 
    exists in the database, and adds it if it's new.

    Returns the (existing or new) Song object from the database.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found at: {file_path}")

    print(f"--- Analyzing file: {os.path.basename(file_path)} ---")
    analysis_result = analyze_music(file_path)

    artist = analysis_result.get('artist')
    title = analysis_result.get('title')

    if not artist or not title or title == "Unknown Title":
        raise ValueError("Could not extract valid artist/title from the audio file.")

    existing_song = db.query(Song).filter(
        func.lower(Song.artist_name) == func.lower(artist),
        func.lower(Song.title) == func.lower(title)
    ).first()

    if existing_song:
        print(f"Found existing song in DB with ID: {existing_song.id}")
        return existing_song
    print("Song is new. Creating new entry in the database.")
    best_genre = _pick_best_genre(analysis_result)

    new_song = Song(
        title=title,
        artist_name=artist,
        genre=best_genre,
        genre_family=genre_family_for(best_genre),
        duration_ms=int(analysis_result.get("duration", 0) * 1000),
        source_type=SourceTypeEnum.user_upload
    )

    # Prefer values computed by the same algorithms used for the MTG-Jamendo catalog
    # import (real Essentia Danceability, the trained valence/arousal model) so that
    # user-uploaded and catalog-seeded songs land on the same comparable scale.
    # Fall back to the cheaper local heuristics only when those aren't available.
    danceability = analysis_result.get("danceability_essentia")
    if danceability is None:
        danceability = analysis_result.get("danceability_local")

    energy = analysis_result.get("arousal")
    if energy is None:
        energy = analysis_result.get("energy_local")

    valence = analysis_result.get("valence")
    if valence is None:
        valence = analysis_result.get("valence_local")

    new_features = AudioFeatures(
        tempo=analysis_result.get("bpm"),
        energy=energy,
        danceability=danceability,
        valence=valence,
        loudness=analysis_result.get("replaygain_db"),
        spectral_centroid=analysis_result.get("spectral_centroid_mean"),
        spectral_bandwidth=analysis_result.get("spectral_bandwidth_mean"),
        mfcc_vector=analysis_result.get("hpcp_mean")
    )

    new_song.features = new_features
    db.add(new_song)
    db.commit()
    db.refresh(new_song)
    mark_index_dirty()
    print(f"Successfully added new song with ID: {new_song.id}")
    return new_song

def recommend_similar_songs(song_id: int, db: Session, limit: int = 5):
    """
    Recommends songs using FAISS vector similarity when available.
    Falls back to a simple BPM heuristic if FAISS is unavailable.
    """
    faiss_results = recommend_by_song_id(song_id, db, limit=limit)
    if faiss_results is not None:
        return faiss_results

    input_song = db.query(Song).filter(Song.id == song_id).first()
    if not input_song or not input_song.features:
        return []

    input_bpm = input_song.features.tempo
    if not input_bpm:
        return []
    input_raw_genres = _raw_genre_set(input_song.raw_genres)
    input_confidence = (input_song.genre_confidence or "").lower()

    all_other_songs = db.query(Song).filter(Song.id != song_id).all()

    scored_songs = []
    for song in all_other_songs:
        if not song.features or not song.features.tempo:
            continue

        bpm_diff = abs(song.features.tempo - input_bpm)
        score = max(0, 100 - bpm_diff * 5)                   

        if input_song.genre and song.genre and input_song.genre == song.genre:
            score += 25 if input_confidence != "low" else 12
        elif input_song.genre_family and song.genre_family and input_song.genre_family == song.genre_family:
            score += 10 if input_confidence != "low" else 5
        elif input_song.genre_family and song.genre_family and input_song.genre_family != song.genre_family:
            score -= 15 if input_confidence == "high" else 8

        if input_song.cluster_id is not None and song.cluster_id is not None:
            if input_song.cluster_id == song.cluster_id:
                score += 20
            else:
                score -= 10

        score += _confidence_score(song.genre_confidence)
        score += _variant_penalty(song.genre_variant_count)
        score += _variant_penalty(input_song.genre_variant_count) * 0.5
        score += _raw_genre_overlap_score(
            input_raw_genres,
            _raw_genre_set(song.raw_genres),
            input_song.genre_confidence,
            song.genre_confidence,
        )

        if score > 20:                                           
            scored_songs.append({
                "id": song.id,
                "title": song.title,
                "artist": song.artist_name,
                "genre": song.genre,
                "genre_family": song.genre_family,
                "raw_genres": song.raw_genres,
                "genre_confidence": song.genre_confidence,
                "genre_variant_count": song.genre_variant_count,
                "cluster_id": song.cluster_id,
                "score": score
            })

    scored_songs.sort(key=lambda x: x["score"], reverse=True)
    return scored_songs[:limit]
