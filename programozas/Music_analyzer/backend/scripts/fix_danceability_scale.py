"""One-off backfill: recompute AudioFeatures.danceability for already-imported
Jamendo songs using the corrected rescale (see import_from_jamendo.py).

The original import clamped Essentia's raw Danceability output (commonly >1.0)
straight to [0,1], saturating ~78% of the catalog at exactly 1.0. This script
re-reads the still-present raw AcousticBrainz JSON files (no re-download
needed) and overwrites the stored value with the corrected rescale.
"""
import json
import os
import sys
from pathlib import Path

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database import SessionLocal
from backend.models import AudioFeatures, ExternalLink, PlatformNameEnum
from backend.services.faiss_recommender import mark_index_dirty
from backend.scripts.import_from_jamendo import load_tags, acousticbrainz_json_path, DEFAULT_DATA_DIR


def run(data_dir: Path = DEFAULT_DATA_DIR) -> None:
    print("Loading track_id -> PATH map...")
    tags = load_tags(data_dir)

    db = SessionLocal()
    try:
        links = (
            db.query(ExternalLink.song_id, ExternalLink.external_id)
            .filter(ExternalLink.platform_name == PlatformNameEnum.jamendo)
            .all()
        )
        print(f"{len(links)} Jamendo-linked songs to check.")

        updated = 0
        missing_json = 0
        missing_value = 0

        for i, (song_id, track_id) in enumerate(links):
            tag_row = tags.get(track_id)
            if not tag_row:
                missing_json += 1
                continue

            json_path = acousticbrainz_json_path(data_dir, tag_row["path"])
            if not json_path.exists():
                missing_json += 1
                continue

            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                raw = data.get("rhythm", {}).get("danceability")
            except Exception:
                raw = None

            if raw is None:
                missing_value += 1
                continue

            corrected = min(max(float(raw), 0.0), 2.5) / 2.5

            feat = db.query(AudioFeatures).filter(AudioFeatures.song_id == song_id).first()
            if feat is None:
                continue
            feat.danceability = corrected
            updated += 1

            if updated % 500 == 0:
                db.commit()
                print(f"  updated {updated}")

        db.commit()
        print(f"Done. updated={updated} missing_json={missing_json} missing_value={missing_value}")
        if updated:
            mark_index_dirty()
    finally:
        db.close()


if __name__ == "__main__":
    run()
