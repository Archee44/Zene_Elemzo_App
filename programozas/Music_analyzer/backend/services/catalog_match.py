from typing import Optional

from sqlalchemy.orm import Session

from backend.models import Song


def find_song_by_title_artist(db: Session, title: str, artist: Optional[str] = None) -> Optional[Song]:
    """Cascading ILIKE match: exact title+artist -> partial title+artist -> title only."""
    title = (title or "").strip()
    artist = (artist or "").strip()
    if not title:
        return None

    if artist:
        exact = (
            db.query(Song)
            .filter(Song.artist_name.ilike(artist), Song.title.ilike(title))
            .first()
        )
        if exact:
            return exact

        partial = (
            db.query(Song)
            .filter(Song.artist_name.ilike(f"%{artist}%"), Song.title.ilike(f"%{title}%"))
            .first()
        )
        if partial:
            return partial

    return db.query(Song).filter(Song.title.ilike(f"%{title}%")).first()
