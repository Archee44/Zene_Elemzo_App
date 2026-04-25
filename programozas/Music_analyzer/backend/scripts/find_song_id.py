import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database import SessionLocal
from backend.models.song import Song
from backend.models.user import UserInteraction                                              
from sqlalchemy import and_

def find_song(artist_query, title_query):
    db = SessionLocal()
    try:
        song = db.query(Song).filter(
            and_(
                Song.artist_name.like(f"%{artist_query}%"),
                Song.title.like(f"%{title_query}%")
            )
        ).first()
        if song:
            print(f"Found song: ID={song.id}, Artist='{song.artist_name}', Title='{song.title}'")
            return song.id
        else:
            print(f"Song with artist like '{artist_query}' and title like '{title_query}' not found.")
            return None
    finally:
        db.close()

if __name__ == "__main__":
    find_song("Showtek", "Dutchi")
