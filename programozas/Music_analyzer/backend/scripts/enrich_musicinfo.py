"""Backfill AudioFeatures.energy / .acousticness for Jamendo-catalog songs from
the Jamendo API's `include=musicinfo` field.

The basic AcousticBrainz low-level JSON we imported from has no classifier
output at all (no energy/valence/acousticness). The Jamendo API itself doesn't
have those either, but `include=musicinfo` gives two coarse, editorially-set
categorical fields we can use as rough proxies:
  - "speed" (verylow..veryhigh)      -> energy
  - "acousticelectric" (acoustic/electric) -> acousticness
There is no equivalent field anywhere for valence - that stays unset for
Jamendo-sourced songs.
"""
import argparse
import os
import sys
import time

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import AudioFeatures, ExternalLink, PlatformNameEnum
from backend.services.faiss_recommender import mark_index_dirty

load_dotenv()

API_URL = "https://api.jamendo.com/v3.0/tracks/"
BATCH_SIZE = 50

SPEED_TO_ENERGY = {
    "verylow": 0.1,
    "low": 0.3,
    "medium": 0.5,
    "high": 0.7,
    "veryhigh": 0.9,
}
ACOUSTICELECTRIC_TO_ACOUSTICNESS = {
    "acoustic": 0.85,
    "electric": 0.15,
}


def enrich_batch(client_id: str, id_to_song: dict) -> int:
    params = [("client_id", client_id), ("format", "json"), ("limit", str(len(id_to_song))), ("include", "musicinfo")]
    params += [("id[]", jid) for jid in id_to_song]
    try:
        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  batch request failed, skipping {len(id_to_song)} tracks: {e}")
        return 0

    updated = 0
    for track in data.get("results", []):
        jid = str(track.get("id") or "")
        song = id_to_song.get(jid)
        if not song:
            continue
        info = track.get("musicinfo") or {}
        energy = SPEED_TO_ENERGY.get((info.get("speed") or "").lower())
        acousticness = ACOUSTICELECTRIC_TO_ACOUSTICNESS.get((info.get("acousticelectric") or "").lower())
        if energy is None and acousticness is None:
            continue
        if energy is not None:
            song.energy = energy
        if acousticness is not None:
            song.acousticness = acousticness
        updated += 1
    return updated


def run(limit: int = None) -> None:
    client_id = os.getenv("JAMENDO_CLIENT_ID")
    if not client_id:
        print("JAMENDO_CLIENT_ID is not set in .env")
        return

    db: Session = SessionLocal()
    try:
        rows = (
            db.query(ExternalLink.external_url, AudioFeatures)
            .join(AudioFeatures, AudioFeatures.song_id == ExternalLink.song_id)
            .filter(ExternalLink.platform_name == PlatformNameEnum.jamendo)
            .all()
        )
        if limit:
            rows = rows[:limit]
        print(f"{len(rows)} Jamendo-linked songs to enrich.")

        total_updated = 0
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            id_to_song = {}
            for external_url, feat in batch:
                jid = (external_url or "").rstrip("/").rsplit("/", 1)[-1]
                if jid.isdigit():
                    id_to_song[jid] = feat

            if id_to_song:
                total_updated += enrich_batch(client_id, id_to_song)

            db.commit()
            print(f"  processed {min(i + BATCH_SIZE, len(rows))}/{len(rows)}, updated so far: {total_updated}")
            time.sleep(0.2)

        print(f"Done. updated={total_updated}")
        if total_updated:
            mark_index_dirty()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill energy/acousticness from Jamendo musicinfo.")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run(limit=args.limit)
