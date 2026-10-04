"""Backfill AudioFeatures.embedding_vector (Discogs-EffNet) and real DEAM
valence/arousal for Jamendo-catalog songs.

The catalog was imported from precomputed low-level AcousticBrainz JSON only
(see import_from_jamendo.py) - no classifier-derived embedding or mood output.
The upload pipeline (music_analyze.py) already runs a Discogs-EffNet embedding
+ a DEAM-trained valence/arousal regressor via Essentia-TensorFlow, fully
local, zero new dependencies (see genre_model.py, valence_arousal_model.py).

This script downloads a short (~60-90s) audio clip per catalog track from the
Jamendo API, runs it through that same pipeline, stores the embedding +
real valence/energy(=arousal), then deletes the clip immediately - no
persistent audio storage, consistent with Jamendo's API terms ("caching...
only to the extent reasonably necessary for the operation of the
Application").

NULL embedding_vector = not yet attempted (retryable on next run).
A confirmed-dead Jamendo link (track no longer returns audio) gets the song
deleted from the catalog entirely - see _delete_dead_song - rather than just
flagged, since an unopenable track is never useful to keep around.
[] (empty list) embedding_vector = attempted, local processing failed (audio
downloaded but embedding/valence-arousal extraction both errored) - the link
itself may still be fine, so the song is kept but excluded from future
eligibility scans; rerun explicitly via --song-ids if desired.
"""
import argparse
import os
import sys
import tempfile
import time
from typing import Optional

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import numpy as np
import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import AudioFeatures, ExternalLink, PlatformNameEnum, Song, PlaylistSong
from backend.models.user import UserInteraction
from backend.services.faiss_recommender import mark_index_dirty
from backend.services.genre_model import extract_discogs_embedding
from backend.services.valence_arousal_model import predict_valence_arousal

load_dotenv()

API_URL = "https://api.jamendo.com/v3.0/tracks/"


def _fetch_audio_urls(client_id: str, track_ids: list) -> Optional[dict]:
    """Returns None if the request itself failed (network/timeout/non-200) -
    a transient, retryable condition. Returns a dict (possibly missing some
    of the requested ids) on any successful response - a ate response that
    simply omits an id means that track has no audio / no longer exists on
    Jamendo, which is permanent, not transient."""
    params = [("client_id", client_id), ("format", "json"), ("limit", str(len(track_ids)))]
    params += [("id[]", tid) for tid in track_ids]
    try:
        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  metadata batch request failed, skipping {len(track_ids)} tracks: {e}")
        return None
    out = {}
    for track in data.get("results", []):
        tid = str(track.get("id") or "")
        url = track.get("audio")
        if tid and url:
            out[tid] = url
    return out


def _delete_dead_song(db: Session, song_id: int) -> None:
    """Confirmed-dead Jamendo link: remove the song entirely rather than just
    sentinel-marking it, so the catalog stays free of unopenable tracks. Mirrors
    the one-off cleanup done earlier in this session - deletes dependent rows
    first (own rating history, playlist references), then the song itself."""
    db.query(UserInteraction).filter(UserInteraction.song_id == song_id).delete(synchronize_session=False)
    db.query(PlaylistSong).filter(PlaylistSong.song_id == song_id).update(
        {PlaylistSong.song_id: None}, synchronize_session=False
    )
    db.query(ExternalLink).filter(ExternalLink.song_id == song_id).delete(synchronize_session=False)
    db.query(AudioFeatures).filter(AudioFeatures.song_id == song_id).delete(synchronize_session=False)
    db.query(Song).filter(Song.id == song_id).delete(synchronize_session=False)


def _download_clip(url: str, cap_bytes: int) -> str:
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    downloaded = 0
    with requests.get(url, stream=True, timeout=20) as resp:
        resp.raise_for_status()
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded >= cap_bytes:
                    break
    return path


def enrich_one(feat: AudioFeatures, audio_url: str, cap_bytes: int) -> bool:
    """Returns True if at least the embedding or the valence/arousal pair was
    written. Always leaves feat.embedding_vector set to something (a real
    vector, or [] as the permanent-failure sentinel) - never leaves it None
    after being attempted, so this track won't be re-picked-up forever."""
    path = None
    try:
        path = _download_clip(audio_url, cap_bytes)

        got_something = False

        frame_matrix = extract_discogs_embedding(path)
        if frame_matrix is not None:
            pooled = frame_matrix.mean(axis=0).astype(np.float32)
            feat.embedding_vector = pooled.tolist()
            got_something = True
        else:
            feat.embedding_vector = []

        va = predict_valence_arousal(path)
        if va:
            feat.valence = va.get("valence")
            feat.energy = va.get("arousal")
            got_something = True

        return got_something
    except Exception as e:
        print(f"    enrich failed: {e}")
        feat.embedding_vector = []
        return False
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def run(limit, song_ids, genre_families, batch_size, audio_cap_bytes, sleep_s):
    client_id = os.getenv("JAMENDO_CLIENT_ID")
    if not client_id:
        print("JAMENDO_CLIENT_ID is not set in .env")
        return

    db: Session = SessionLocal()
    try:
        query = (
            db.query(ExternalLink.external_url, AudioFeatures)
            .join(AudioFeatures, AudioFeatures.song_id == ExternalLink.song_id)
            .filter(ExternalLink.platform_name == PlatformNameEnum.jamendo)
            .filter(AudioFeatures.embedding_vector.is_(None))
        )
        if song_ids:
            query = query.filter(AudioFeatures.song_id.in_(song_ids))
        elif genre_families:
            lowered = [g.strip().lower() for g in genre_families]
            query = query.join(Song, Song.id == ExternalLink.song_id).filter(
                Song.genre_family.in_(lowered)
            )

        rows = query.all()
        if limit:
            rows = rows[:limit]
        print(f"{len(rows)} eligible Jamendo-linked songs.")

        total_updated = 0
        total_failed = 0
        total_skipped = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            # ExternalLink.external_id stores the MTG-Jamendo dataset's own
            # zero-padded "track_0123456" identifier, not Jamendo's plain
            # numeric API track id - the real id is the last path segment of
            # external_url (e.g. https://www.jamendo.com/track/123456),
            # matching the parsing already used in enrich_musicinfo.py.
            def _real_track_id(url):
                return (url or "").rstrip("/").rsplit("/", 1)[-1]

            batch_with_ids = [(feat, _real_track_id(url)) for url, feat in batch]
            track_ids = [tid for _feat, tid in batch_with_ids if tid.isdigit()]
            audio_urls = _fetch_audio_urls(client_id, track_ids)

            if audio_urls is None:
                # The metadata request itself failed - genuinely transient
                # (network/timeout). Leave every song in this batch as NULL
                # so it's retried on the next run.
                print(f"  batch metadata request failed, {len(batch_with_ids)} songs left for retry")
                total_skipped += len(batch_with_ids)
                continue

            for feat, tid in batch_with_ids:
                url = audio_urls.get(tid)
                if not url:
                    # The request succeeded but this id wasn't in the
                    # results - the track has no audio or no longer exists
                    # on Jamendo. Confirmed dead link: remove the song from
                    # the catalog entirely rather than just sentinel-marking
                    # it, so users never see something they can't open.
                    print(f"  song_id={feat.song_id} jamendo_id={tid}: no longer available on Jamendo, deleting")
                    _delete_dead_song(db, feat.song_id)
                    db.commit()
                    total_failed += 1
                    continue
                ok = enrich_one(feat, url, audio_cap_bytes)
                db.commit()
                if ok:
                    total_updated += 1
                else:
                    total_failed += 1
                time.sleep(sleep_s)

            print(f"  processed {min(i + batch_size, len(rows))}/{len(rows)} - "
                  f"updated={total_updated} failed={total_failed} skipped={total_skipped}")

        print(f"Done. updated={total_updated} failed={total_failed} skipped={total_skipped}")
        if total_updated:
            mark_index_dirty()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill embedding_vector + real valence/energy from audio.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--song-ids", type=str, default=None, help="Comma-separated explicit song IDs")
    parser.add_argument("--genre-family", type=str, default=None, help="Comma-separated genre_family filter")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--audio-cap-bytes", type=int, default=int(2.5 * 1024 * 1024))
    parser.add_argument("--sleep", type=float, default=0.3)
    args = parser.parse_args()

    song_ids = [int(x) for x in args.song_ids.split(",")] if args.song_ids else None
    genre_families = args.genre_family.split(",") if args.genre_family else None

    run(
        limit=args.limit,
        song_ids=song_ids,
        genre_families=genre_families,
        batch_size=args.batch_size,
        audio_cap_bytes=args.audio_cap_bytes,
        sleep_s=args.sleep,
    )
