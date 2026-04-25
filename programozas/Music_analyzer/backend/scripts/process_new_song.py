import sys
import os
import json

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database import SessionLocal
from backend.models import Song, AudioFeatures, SourceTypeEnum
from backend.services.music_analyze import analyze_music
from sqlalchemy.orm import Session

def process_and_save_song(file_path: str, db: Session):
    """
    Analyzes a music file, checks if it exists in the DB, and adds it if it's new.
    """
    print(f"--- Starting analysis for: {os.path.basename(file_path)} ---")
    try:
        analysis_result = analyze_music(file_path)
    except Exception as e:
        print(f"Error during analysis: {e}")
        return

    artist = analysis_result.get('artist')
    title = analysis_result.get('title')

    if not artist or not title or title == "Unknown Title":
        print("Could not extract valid artist/title from the song. Skipping DB insertion.")
        return

    print(f"Analysis complete. Found Artist: '{artist}', Title: '{title}'")

    existing_song = db.query(Song).filter(
        Song.artist_name.ilike(f"%{artist}%"),
        Song.title.ilike(f"%{title}%")
    ).first()

    if existing_song:
        print(f"Song already exists in the database with ID: {existing_song.id}. No changes made.")
        return existing_song
    print("Song is new. Creating new database entries.")

    try:
        new_song = Song(
            title=title,
            artist_name=artist,
            duration_ms=int(analysis_result.get("duration", 0) * 1000),                        
            source_type=SourceTypeEnum.user_upload,                        
        )

        new_features = AudioFeatures(
            tempo=analysis_result.get("bpm"),
            energy=analysis_result.get("energy_local"),
            danceability=analysis_result.get("danceability_local"),
            valence=analysis_result.get("valence_local"),
            acousticness=analysis_result.get("local_feats", {}).get("hpr"),                                                 
            loudness=analysis_result.get("replaygain_db"),
            spectral_centroid=analysis_result.get("spectral_centroid_mean"),
            spectral_bandwidth=analysis_result.get("spectral_bandwidth_mean"),
            mfcc_vector=analysis_result.get("hpcp_mean"),                                            
            embedding_vector=None                                              
        )

        new_song.features = new_features
        db.add(new_song)
        db.commit()
        db.refresh(new_song)
        print(f"Successfully added new song to database with ID: {new_song.id}")
        return new_song

    except Exception as e:
        print(f"Error during database insertion: {e}")
        db.rollback()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_new_song.py <path_to_audio_file>")
        sys.exit(1)
    file_to_process = sys.argv[1]
    if not os.path.exists(file_to_process):
        docker_path = os.path.join('/app', file_to_process)
        if not os.path.exists(docker_path):
            print(f"Error: File not found at '{file_to_process}' or '{docker_path}'")
            sys.exit(1)
        file_to_process = docker_path

    db_session = SessionLocal()
    try:
        process_and_save_song(file_to_process, db_session)
    finally:
        db_session.close()
        print("--- Process finished. DB session closed. ---")
