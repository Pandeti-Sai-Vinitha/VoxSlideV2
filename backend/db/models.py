# models.py
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Float
from sqlalchemy.sql import func
from .database import Base

# We store status as a string for SQLite compatibility
# Allowed values: new | processing | completed | failed

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # 'pdf' | 'docx'
    status = Column(String, nullable=False, default="new")
    stage = Column(String)  # e.g., 'generating_slides', 'slides_generated', etc.
    progress = Column(Integer)  # Optional progress percentage (0-100)
    error_message = Column(String)  # Error details if status is 'failed'
    size_bytes = Column(Integer)
    path = Column(String)
    basename = Column(String)

    # New fields for persistent slide info
    slides_count = Column(Integer, default=0)  # Number of slides generated
    generated_at = Column(DateTime(timezone=True))  # When slides were generated
    duration = Column(Float)  # Video duration in seconds
    output_type = Column(String, default='pptx')  # Output type: pptx or pptx+video

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)