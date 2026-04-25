from __future__ import annotations

import os
import re
from typing import Dict, Optional

import requests

from backend.models import Song

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2"
MUSICBRAINZ_USER_AGENT = os.getenv(
    "MUSICBRAINZ_USER_AGENT",
    "MeloDive/0.1 ( local-dev )",
)

def _normalize(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())

def _build_headers() -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "User-Agent": MUSICBRAINZ_USER_AGENT,
    }

def search_best_recording(title: str, artist_name: str) -> Optional[Dict]:
    norm_title = _normalize(title)
    norm_artist = _normalize(artist_name)
    if not norm_title or not norm_artist:
        return None

    query = f'recording:"{title}" AND artist:"{artist_name}"'
    try:
        resp = requests.get(
            f"{MUSICBRAINZ_BASE_URL}/recording",
            params={
                "query": query,
                "fmt": "json",
                "limit": 10,
            },
            headers=_build_headers(),
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as exc:
        print("[musicbrainz] search request failed:", exc)
        return None

    data = resp.json() or {}
    recordings = data.get("recordings") or []
    if not recordings:
        return None

    def score_recording(rec: Dict) -> int:
        score = int(rec.get("score") or 0)
        rec_title = _normalize(rec.get("title"))
        if rec_title == norm_title:
            score += 30

        for credit in rec.get("artist-credit") or []:
            credited = _normalize(credit.get("name"))
            if credited == norm_artist:
                score += 30
                break
            artist_obj = credit.get("artist") or {}
            artist_name_mb = _normalize(artist_obj.get("name"))
            if artist_name_mb == norm_artist:
                score += 30
                break
        return score

    recordings.sort(key=score_recording, reverse=True)
    return recordings[0]

def enrich_song_from_musicbrainz(song: Song) -> Optional[Dict]:
    match = search_best_recording(song.title, song.artist_name)
    if not match:
        return None

    release_list = match.get("releases") or []
    primary_release = release_list[0] if release_list else {}
    release_date = (primary_release.get("date") or "").strip()

    release_year = None
    if len(release_date) >= 4 and release_date[:4].isdigit():
        release_year = int(release_date[:4])

    artist_credit = match.get("artist-credit") or []
    mb_artist_name = None
    if artist_credit:
        first_credit = artist_credit[0] or {}
        mb_artist_name = first_credit.get("name") or (first_credit.get("artist") or {}).get("name")

    return {
        "mbid": match.get("id"),
        "title": match.get("title") or song.title,
        "artist_name": mb_artist_name or song.artist_name,
        "album_name": primary_release.get("title") or song.album_name,
        "release_year": release_year if release_year is not None else song.release_year,
        "raw_match_score": int(match.get("score") or 0),
    }
