import enum
from sqlalchemy import (
    Column, 
    Integer, 
    DateTime, 
    ForeignKey, 
    Enum
)
from sqlalchemy.sql import func
from ..database import Base

class ProcessingStatusEnum(enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"

class ProcessingQueue(Base):
    __tablename__ = "processing_queue"

    id = Column(Integer, primary_key=True, index=True)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=False, index=True)
    status = Column(Enum(ProcessingStatusEnum), default=ProcessingStatusEnum.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
