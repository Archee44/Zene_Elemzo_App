import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from urllib.parse import urlencode

import requests
from sqlalchemy.orm import Session

from backend.models.user import UserLinkedAccount, LinkedProviderEnum
from backend.services.auth_utils import issue_connect_state
from backend.services.music_analyze import cleaned_title

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://127.0.0.1:5000/api/auth/youtube/callback"
SCOPE = "https://www.googleapis.com/auth/youtube.readonly"

EXPIRY_BUFFER = timedelta(seconds=60)


def build_authorize_url(user_id: int) -> str:
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": issue_connect_state(user_id),
        "access_type": "offline",
        # Force the account chooser as well as consent - otherwise Google silently
        # reuses whatever Google session is already active in the browser, which
        # can be a different account than the one added under Test users.
        "prompt": "select_account consent",
        "include_granted_scopes": "true",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> Optional[dict]:
    res = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    if res.status_code != 200:
        return None
    return res.json()


def _refresh_access_token(refresh_token: str) -> Optional[dict]:
    res = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    if res.status_code != 200:
        return None
    return res.json()


def get_linked_account(user_id: int, db: Session) -> Optional[UserLinkedAccount]:
    return (
        db.query(UserLinkedAccount)
        .filter(UserLinkedAccount.user_id == user_id, UserLinkedAccount.provider == LinkedProviderEnum.youtube)
        .first()
    )


def get_valid_access_token(user_id: int, db: Session) -> Optional[str]:
    account = get_linked_account(user_id, db)
    if not account or not account.access_token:
        return None

    now = datetime.now(timezone.utc)
    expires_at = account.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        # SQLite round-trips DateTime(timezone=True) values as naive - we always
        # write these in UTC, so re-attach that before comparing to an aware "now".
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at - EXPIRY_BUFFER > now:
        return account.access_token

    if not account.refresh_token:
        return None

    refreshed = _refresh_access_token(account.refresh_token)
    if not refreshed:
        # Refresh token revoked/expired - clear the tokens but keep the row so
        # "connection broke" can be told apart from "never connected".
        account.access_token = None
        account.expires_at = None
        db.commit()
        return None

    account.access_token = refreshed["access_token"]
    expires_in = refreshed.get("expires_in", 3600)
    account.expires_at = now + timedelta(seconds=expires_in)
    db.commit()
    return account.access_token


def list_playlists(access_token: str) -> List[dict]:
    playlists = []
    page_token = None
    while True:
        params = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/playlists",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if res.status_code != 200:
            break
        data = res.json()
        for item in data.get("items", []):
            playlists.append({
                "id": item["id"],
                "title": item["snippet"]["title"],
                "item_count": item.get("contentDetails", {}).get("itemCount", 0),
                "thumbnail": (item["snippet"].get("thumbnails", {}).get("default") or {}).get("url"),
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return playlists


def list_playlist_items(access_token: str, playlist_id: str) -> List[dict]:
    items = []
    page_token = None
    while True:
        params = {"part": "snippet", "playlistId": playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if res.status_code != 200:
            break
        data = res.json()
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            title = snippet.get("title")
            if not title or title in ("Deleted video", "Private video"):
                continue
            items.append({
                "title": title,
                "channel_title": snippet.get("videoOwnerChannelTitle") or snippet.get("channelTitle"),
                "position": snippet.get("position"),
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items


def parse_video_title(raw_title: str) -> Tuple[str, Optional[str]]:
    """Best-effort split of a noisy YouTube video title into (title, artist_guess)."""
    if " - " in raw_title:
        maybe_artist, maybe_title = raw_title.split(" - ", 1)
        return cleaned_title(maybe_title), cleaned_title(maybe_artist) or None
    return cleaned_title(raw_title), None
