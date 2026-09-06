import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
    Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class SourceTypeEnum(enum.Enum):
    static = "static"
    api = "api"
    user_upload = "user_upload"

class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    mbid = Column(String, unique=True, index=True, nullable=True)
    title = Column(String, index=True, nullable=False)
    artist_name = Column(String, index=True, nullable=False)
    album_name = Column(String, nullable=True)
    genre = Column(String, index=True, nullable=True)
    genre_family = Column(String, index=True, nullable=True)
    raw_genres = Column(String, nullable=True)
    genre_confidence = Column(String, index=True, nullable=True)
    genre_variant_count = Column(Integer, nullable=True)
    cluster_id = Column(Integer, index=True, nullable=True)
    release_year = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    source_type = Column(Enum(SourceTypeEnum))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    features = relationship("AudioFeatures", back_populates="song", uselist=False)
    external_links = relationship("ExternalLink", back_populates="song")
    interactions = relationship("UserInteraction", back_populates="song")

class AudioFeatures(Base):
    __tablename__ = "audio_features"

    song_id = Column(Integer, ForeignKey("songs.id"), primary_key=True)
    tempo = Column(Float, nullable=True)
    energy = Column(Float, nullable=True)
    danceability = Column(Float, nullable=True)
    valence = Column(Float, nullable=True)
    acousticness = Column(Float, nullable=True)
    loudness = Column(Float, nullable=True)
    spectral_centroid = Column(Float, nullable=True)
    spectral_bandwidth = Column(Float, nullable=True)
    mfcc_vector = Column(JSON, nullable=True)
    embedding_vector = Column(JSON, nullable=True)

    song = relationship("Song", back_populates="features")

class PlatformNameEnum(enum.Enum):
    spotify = "spotify"
    youtube = "youtube"
    deezer = "deezer"
    jamendo = "jamendo"

class ExternalLink(Base):
    __tablename__ = "external_links"

    id = Column(Integer, primary_key=True, index=True)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    platform_name = Column(Enum(PlatformNameEnum), nullable=False)
    external_url = Column(String, nullable=False)
    external_id = Column(String, index=True, nullable=True)
    # NULL = not checked yet, True/False = result of the last liveness check
    link_is_valid = Column(Boolean, nullable=True, index=True)
    link_checked_at = Column(DateTime(timezone=True), nullable=True)

    song = relationship("Song", back_populates="external_links")
