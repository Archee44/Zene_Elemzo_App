from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite adatbázis (music.db)
SQLALCHEMY_DATABASE_URL = "sqlite:///./music.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():

    from backend.models.song import Song, AudioFeatures, ExternalLink
    from backend.models.user import User, UserInteraction, UserProfile
    from backend.models.queue import ProcessingQueue
    
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    _ensure_schema_updates()
    print("Database tables created.")


def _ensure_schema_updates():
    inspector = inspect(engine)
    song_columns = {col["name"] for col in inspector.get_columns("songs")}

    with engine.begin() as conn:
        if "genre" not in song_columns:
            conn.execute(text("ALTER TABLE songs ADD COLUMN genre VARCHAR"))
        if "genre_family" not in song_columns:
            conn.execute(text("ALTER TABLE songs ADD COLUMN genre_family VARCHAR"))
        if "raw_genres" not in song_columns:
            conn.execute(text("ALTER TABLE songs ADD COLUMN raw_genres VARCHAR"))
        if "genre_confidence" not in song_columns:
            conn.execute(text("ALTER TABLE songs ADD COLUMN genre_confidence VARCHAR"))
        if "genre_variant_count" not in song_columns:
            conn.execute(text("ALTER TABLE songs ADD COLUMN genre_variant_count INTEGER"))
        if "cluster_id" not in song_columns:
            conn.execute(text("ALTER TABLE songs ADD COLUMN cluster_id INTEGER"))
