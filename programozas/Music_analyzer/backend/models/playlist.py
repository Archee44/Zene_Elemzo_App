import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class PlaylistSourceEnum(enum.Enum):
    youtube = "youtube"
    spotify = "spotify"
    manual = "manual"


class Playlist(Base):
    __tablename__ = "playlists"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "external_id", name="uq_playlist_user_source_external"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    source = Column(Enum(PlaylistSourceEnum), nullable=False)
    external_id = Column(String, nullable=True, index=True)
    imported_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("PlaylistSong", back_populates="playlist", cascade="all, delete-orphan")


class PlaylistSong(Base):
    __tablename__ = "playlist_songs"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False, index=True)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=True)
    position = Column(Integer, nullable=True)
    raw_title = Column(String, nullable=False)
    raw_artist = Column(String, nullable=True)

    playlist = relationship("Playlist", back_populates="items")
    song = relationship("Song")
