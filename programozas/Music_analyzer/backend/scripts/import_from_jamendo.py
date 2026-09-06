"""Import MTG-Jamendo tracks (metadata + tags + AcousticBrainz features) into the DB.

Expects the following under --data-dir (default: <project_root>/data/mtg_jamendo):
  autotagging.tsv        TRACK_ID  ARTIST_ID  ALBUM_ID  PATH  DURATION  TAGS...
  raw.meta.tsv            TRACK_ID  ARTIST_ID  ALBUM_ID  TRACK_NAME  ARTIST_NAME  ALBUM_NAME  RELEASEDATE  URL
  acousticbrainz/<PATH with .json instead of .mp3>   precomputed Essentia low-level/rhythm/tonal JSON

Only tracks whose AcousticBrainz JSON was actually downloaded (i.e. whose shard was
fetched) are imported - see README note in the project chat about downloading a subset
of the 100 shards instead of the whole dataset.
"""
import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Song, AudioFeatures, ExternalLink, SourceTypeEnum, PlatformNameEnum
from backend.services.genre_taxonomy import genre_family_for
from backend.services.faiss_recommender import mark_index_dirty

DEFAULT_DATA_DIR = Path(project_root) / "data" / "mtg_jamendo"


def load_meta(data_dir: Path) -> Dict[str, dict]:
    meta: Dict[str, dict] = {}
    with open(data_dir / "raw.meta.tsv", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            meta[row["TRACK_ID"]] = {
                "title": (row.get("TRACK_NAME") or "").strip(),
                "artist": (row.get("ARTIST_NAME") or "").strip(),
                "album": (row.get("ALBUM_NAME") or "").strip() or None,
                "release_date": row.get("RELEASEDATE"),
                "url": row.get("URL"),
            }
    return meta


def load_tags(data_dir: Path) -> Dict[str, dict]:
    tracks: Dict[str, dict] = {}
    with open(data_dir / "autotagging.tsv", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader, None)  # header
        for row in reader:
            if len(row) < 6:
                continue
            track_id, _artist_id, _album_id, path, duration, *raw_tags = row
            genres, moods, instruments = [], [], []
            for tag in raw_tags:
                if tag.startswith("genre---"):
                    genres.append(tag[len("genre---"):])
                elif tag.startswith("mood/theme---"):
                    moods.append(tag[len("mood/theme---"):])
                elif tag.startswith("instrument---"):
                    instruments.append(tag[len("instrument---"):])
            tracks[track_id] = {
                "path": path,
                "duration": float(duration) if duration else 0.0,
                "genres": genres,
                "moods": moods,
                "instruments": instruments,
            }
    return tracks


def acousticbrainz_json_path(data_dir: Path, relative_mp3_path: str) -> Path:
    return data_dir / "acousticbrainz" / relative_mp3_path.replace(".mp3", ".json")


def extract_features(json_path: Path) -> Optional[dict]:
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    try:
        rhythm = data.get("rhythm", {})
        tonal = data.get("tonal", {})
        lowlevel = data.get("lowlevel", {})
        audio_props = data.get("metadata", {}).get("audio_properties", {})

        danceability_raw = rhythm.get("danceability")
        danceability = min(max(float(danceability_raw), 0.0), 1.0) if danceability_raw is not None else None

        # Essentia's lowlevel.spectral_spread is a variance (Hz^2); our own pipeline's
        # spectral_bandwidth_mean is a standard deviation (Hz) - sqrt() to match units.
        spread_variance = (lowlevel.get("spectral_spread") or {}).get("mean")
        spectral_bandwidth = math.sqrt(spread_variance) if spread_variance and spread_variance > 0 else None

        return {
            "bpm": rhythm.get("bpm"),
            "danceability": danceability,
            "key": tonal.get("key_key"),
            "scale": tonal.get("key_scale"),
            "key_strength": tonal.get("key_strength"),
            "loudness": audio_props.get("replay_gain"),
            "spectral_centroid": (lowlevel.get("spectral_centroid") or {}).get("mean"),
            "spectral_spread": spectral_bandwidth,
            "mfcc_mean": (lowlevel.get("mfcc") or {}).get("mean"),
        }
    except Exception:
        return None


def _parse_year(release_date: Optional[str]) -> Optional[int]:
    if not release_date:
        return None
    try:
        return int(release_date[:4])
    except (TypeError, ValueError):
        return None


def import_data(data_dir: Path, limit: Optional[int] = None, commit_every: int = 200) -> None:
    print(f"Loading metadata from {data_dir} ...")
    meta = load_meta(data_dir)
    tags = load_tags(data_dir)
    print(f"{len(tags)} tagged tracks, {len(meta)} with human-readable metadata.")

    db: Session = SessionLocal()
    try:
        existing_jamendo_ids = {
            link.external_id
            for link in db.query(ExternalLink.external_id).filter(
                ExternalLink.platform_name == PlatformNameEnum.jamendo
            )
        }
        print(f"{len(existing_jamendo_ids)} Jamendo tracks already in the DB (will be skipped).")

        imported = 0
        skipped_no_features = 0
        skipped_no_meta = 0
        skipped_duplicate_title = 0

        for track_id, tag_row in tags.items():
            if limit is not None and imported >= limit:
                break
            if track_id in existing_jamendo_ids:
                continue

            m = meta.get(track_id)
            if not m or not m["title"] or not m["artist"]:
                skipped_no_meta += 1
                continue

            json_path = acousticbrainz_json_path(data_dir, tag_row["path"])
            if not json_path.exists():
                skipped_no_features += 1
                continue

            feats = extract_features(json_path)
            if not feats or feats.get("bpm") is None:
                skipped_no_features += 1
                continue

            dup = (
                db.query(Song.id)
                .filter(
                    func.lower(Song.artist_name) == m["artist"].lower(),
                    func.lower(Song.title) == m["title"].lower(),
                )
                .first()
            )
            if dup:
                skipped_duplicate_title += 1
                continue

            all_tags = tag_row["genres"] + tag_row["moods"] + tag_row["instruments"]
            best_genre = tag_row["genres"][0] if tag_row["genres"] else None

            new_song = Song(
                title=m["title"],
                artist_name=m["artist"],
                album_name=m["album"],
                genre=best_genre,
                genre_family=genre_family_for(best_genre),
                raw_genres="|".join(all_tags) or None,
                genre_confidence="high" if tag_row["genres"] else None,
                genre_variant_count=len(tag_row["genres"]) or None,
                release_year=_parse_year(m["release_date"]),
                duration_ms=int(tag_row["duration"] * 1000),
                source_type=SourceTypeEnum.static,
            )
            new_features = AudioFeatures(
                tempo=feats["bpm"],
                danceability=feats["danceability"],
                loudness=feats["loudness"],
                spectral_centroid=feats["spectral_centroid"],
                spectral_bandwidth=feats["spectral_spread"],
                mfcc_vector=feats["mfcc_mean"],
            )
            new_link = ExternalLink(
                platform_name=PlatformNameEnum.jamendo,
                external_id=track_id,
                external_url=m["url"] or f"https://www.jamendo.com/track/{track_id}",
            )

            new_song.features = new_features
            new_song.external_links.append(new_link)
            db.add(new_song)
            imported += 1

            if imported % commit_every == 0:
                db.commit()
                print(f"Committed. Imported so far: {imported}")

        db.commit()
        print(
            f"Done. Imported: {imported}, "
            f"skipped (no acousticbrainz json downloaded): {skipped_no_features}, "
            f"skipped (no title/artist metadata): {skipped_no_meta}, "
            f"skipped (duplicate title/artist already in DB): {skipped_duplicate_title}"
        )
        if imported:
            mark_index_dirty()
    except Exception as e:
        db.rollback()
        print(f"An error occurred: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import MTG-Jamendo tracks into the DB.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--limit", type=int, default=None, help="Max number of new tracks to import.")
    parser.add_argument("--commit-every", type=int, default=200)
    args = parser.parse_args()
    import_data(args.data_dir, limit=args.limit, commit_every=args.commit_every)
