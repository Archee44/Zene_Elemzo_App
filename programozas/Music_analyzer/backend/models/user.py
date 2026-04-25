import enum
from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    ForeignKey, 
    Enum,
    Float,
    JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interactions = relationship("UserInteraction", back_populates="user")
    profile = relationship("UserProfile", back_populates="user", uselist=False)

class InteractionTypeEnum(enum.Enum):
    play = "play"
    like = "like"
    skip = "skip"
    upload = "upload"
    search_result_click = "search_result_click"

class UserInteraction(Base):
    __tablename__ = "user_interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    interaction_type = Column(Enum(InteractionTypeEnum), nullable=False)
    interaction_weight = Column(Float, default=1.0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="interactions")
    song = relationship("Song", back_populates="interactions")

class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    profile_vector = Column(JSON, nullable=True)
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="profile")
