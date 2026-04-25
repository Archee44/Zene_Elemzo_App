import csv
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database import SessionLocal
from backend.models.song import Song, AudioFeatures, ExternalLink, SourceTypeEnum, PlatformNameEnum
from backend.models.user import User, UserInteraction                                                        
from backend.services.genre_taxonomy import genre_family_for
from sqlalchemy.orm import Session

def seed_if_empty() -> bool:
    db: Session = SessionLocal()
    try:
        has_songs = db.query(Song.id).first() is not None
    finally:
        db.close()

    if has_songs:
        print("Database already contains songs. Skipping CSV seed.")
        return False

    print("Database is empty. Importing seed data from CSV.")
    import_data()
    return True

def import_data():
    cleaned_csv_path = os.path.join(project_root, 'cleaned_dataset.csv')
    csv_path = cleaned_csv_path if os.path.exists(cleaned_csv_path) else os.path.join(project_root, 'dataset.csv')
    db: Session = SessionLocal()
    print(f"Using CSV source: {os.path.basename(csv_path)}")
    existing_links = (
        db.query(
            ExternalLink.external_id,
            ExternalLink.song_id,
            Song.genre,
            Song.genre_family,
            Song.raw_genres,
            Song.genre_confidence,
            Song.genre_variant_count,
        )
        .join(Song, Song.id == ExternalLink.song_id)
        .filter(ExternalLink.platform_name == PlatformNameEnum.spotify)
        .all()
    )
    existing_track_ids = {link.external_id for link in existing_links}
    existing_song_ids_needing_genre = {
        link.external_id: link.song_id
        for link in existing_links
        if link.external_id and (
            not link.genre
            or not link.genre_family
            or not link.raw_genres
            or not link.genre_confidence
            or link.genre_variant_count is None
        )
    }
    print(f"Found {len(existing_track_ids)} existing tracks in the database.")

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                track_id = row.get('track_id')

                if not track_id:
                    continue

                if track_id in existing_track_ids:
                    existing_song_id = existing_song_ids_needing_genre.get(track_id)
                    csv_genre = row.get('track_genre') or None
                    if existing_song_id:
                        csv_genre_family = genre_family_for(csv_genre)
                        csv_variant_count = row.get("genre_variant_count")
                        try:
                            csv_variant_count_int = int(csv_variant_count) if csv_variant_count not in (None, "") else None
                        except (TypeError, ValueError):
                            csv_variant_count_int = None
                        db.query(Song).filter(Song.id == existing_song_id).update(
                            {
                                "genre": csv_genre,
                                "genre_family": csv_genre_family,
                                "raw_genres": row.get("raw_genres") or None,
                                "genre_confidence": row.get("genre_confidence") or None,
                                "genre_variant_count": csv_variant_count_int,
                            },
                            synchronize_session=False,
                        )
                        existing_song_ids_needing_genre.pop(track_id, None)
                    continue

                new_song = Song(
                    title=row.get('track_name', 'Unknown Title'),
                    artist_name=row.get('artists', 'Unknown Artist'),
                    album_name=row.get('album_name'),
                    genre=row.get('track_genre') or None,
                    genre_family=genre_family_for(row.get('track_genre')),
                    raw_genres=row.get('raw_genres') or None,
                    genre_confidence=row.get('genre_confidence') or None,
                    genre_variant_count=int(row.get('genre_variant_count')) if row.get('genre_variant_count') not in (None, '') else None,
                    duration_ms=int(row.get('duration_ms', 0)),
                    source_type=SourceTypeEnum.static
                )
                new_features = AudioFeatures(
                    danceability=float(row.get('danceability', 0.0)),
                    energy=float(row.get('energy', 0.0)),
                    loudness=float(row.get('loudness', 0.0)),
                    valence=float(row.get('valence', 0.0)),
                    acousticness=float(row.get('acousticness', 0.0)),
                    tempo=float(row.get('tempo', 0.0)),
                    spectral_centroid=None,
                    spectral_bandwidth=None,
                    mfcc_vector=None,
                    embedding_vector=None
                )
                new_link = ExternalLink(
                    platform_name=PlatformNameEnum.spotify,
                    external_id=track_id,
                    external_url=f"https://open.spotify.com/track/{track_id}"
                )

                new_song.features = new_features
                new_song.external_links.append(new_link)

                db.add(new_song)
                existing_track_ids.add(track_id)
                count += 1
                if count % 100 == 0:
                    db.commit()
                    print(f"Committed 100 tracks. Total imported: {count}")

            db.commit()
            print(f"Final commit. Total imported: {count}")
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()
        print("Database session closed.")

if __name__ == "__main__":
    import_data()
