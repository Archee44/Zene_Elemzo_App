"""Check which Jamendo ExternalLink rows still point to a real track.

Why: jamendo.com is a client-rendered site behind bot protection - a plain HTTP
GET/HEAD to a track page almost always hangs or gets blocked, and even when it
doesn't, a dead track can still render a 200-status "not found" page (soft-404).
So instead of scraping the site, this hits the official Jamendo API
(https://api.jamendo.com/v3.0/tracks/), which reports track existence directly
and, as a bonus, gives back a fresh canonical share URL.

Requires a free client_id from https://devportal.jamendo.com/ (self-service
signup) set as JAMENDO_CLIENT_ID in the project .env.
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import ExternalLink, PlatformNameEnum

load_dotenv()

API_URL = "https://api.jamendo.com/v3.0/tracks/"
BATCH_SIZE = 50


def _extract_jamendo_id(link: ExternalLink) -> str:
    # external_id is the MTG track_id ("track_0000214"); the Jamendo API wants
    # the raw numeric id, which lives at the end of external_url instead.
    url = (link.external_url or "").rstrip("/")
    tail = url.rsplit("/", 1)[-1]
    return tail if tail.isdigit() else ""


def validate_batch(client_id: str, id_to_link: dict) -> None:
    # The Jamendo API batch-lookup array param is PHP-style "id[]=...", not a
    # repeated bare "id=..." (that silently matches nothing) nor comma-joined
    # (that errors: "accept only Integer values").
    params = [("client_id", client_id), ("format", "json"), ("limit", str(len(id_to_link)))]
    params += [("id[]", jid) for jid in id_to_link]
    try:
        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  batch request failed, leaving {len(id_to_link)} links unchecked: {e}")
        return

    found_ids = set()
    for track in data.get("results", []):
        jid = str(track.get("id") or "")
        if not jid:
            continue
        found_ids.add(jid)
        link = id_to_link[jid]
        link.link_is_valid = True
        link.link_checked_at = datetime.now(timezone.utc)
        share_url = track.get("shareurl")
        if share_url:
            link.external_url = share_url

    for jid, link in id_to_link.items():
        if jid not in found_ids:
            link.link_is_valid = False
            link.link_checked_at = datetime.now(timezone.utc)


def run(limit: int = None, only_unchecked: bool = True) -> None:
    client_id = os.getenv("JAMENDO_CLIENT_ID")
    if not client_id:
        print("JAMENDO_CLIENT_ID is not set in .env - get a free one at https://devportal.jamendo.com/ first.")
        return

    db: Session = SessionLocal()
    try:
        q = db.query(ExternalLink).filter(ExternalLink.platform_name == PlatformNameEnum.jamendo)
        if only_unchecked:
            q = q.filter(ExternalLink.link_checked_at.is_(None))
        if limit:
            q = q.limit(limit)
        links = q.all()
        print(f"Checking {len(links)} Jamendo links...")

        checked = 0
        for i in range(0, len(links), BATCH_SIZE):
            batch = links[i:i + BATCH_SIZE]
            id_to_link = {}
            for link in batch:
                jid = _extract_jamendo_id(link)
                if jid:
                    id_to_link[jid] = link
                else:
                    link.link_is_valid = False
                    link.link_checked_at = datetime.now(timezone.utc)

            if id_to_link:
                validate_batch(client_id, id_to_link)

            db.commit()
            checked += len(batch)
            print(f"  checked {checked}/{len(links)}")
            time.sleep(0.2)  # be polite to the free tier rate limit

        valid = db.query(ExternalLink).filter(
            ExternalLink.platform_name == PlatformNameEnum.jamendo,
            ExternalLink.link_is_valid.is_(True),
        ).count()
        invalid = db.query(ExternalLink).filter(
            ExternalLink.platform_name == PlatformNameEnum.jamendo,
            ExternalLink.link_is_valid.is_(False),
        ).count()
        print(f"Done. valid={valid} invalid={invalid}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Jamendo external links against the live API.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--recheck-all", action="store_true", help="Re-check links that already have a result, not just unchecked ones.")
    args = parser.parse_args()
    run(limit=args.limit, only_unchecked=not args.recheck_all)
