from backend.models import Song, AudioFeatures, SourceTypeEnum

def save_track(db, track_data, file_path: str):
    """
    Backward-compatible helper that stores an analyzed track
    using the current Song + AudioFeatures schema.
    """
    song = Song(
        title=track_data.get("title") or "Unknown Title",
        artist_name=track_data.get("artist") or "Unknown Artist",
        duration_ms=int((track_data.get("duration") or 0) * 1000),
        source_type=SourceTypeEnum.user_upload,
    )

    features = AudioFeatures(
        tempo=track_data.get("bpm"),
        energy=track_data.get("energy"),
        danceability=track_data.get("danceability_score"),
        valence=track_data.get("valence"),
        loudness=track_data.get("rms"),
    )

    song.features = features
    db.add(song)
    db.commit()
    db.refresh(song)
    return song
