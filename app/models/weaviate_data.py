from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, func, ForeignKey, Enum
from models.base import Base
import enum


class WeaviateDataStatusEnum(enum.Enum):
    """
    Enum for task run status values.
    """
    IN_PROGRESS = "IN_PROGRESS"
    CANCELLED = "CANCELLED"
    EXIT_WITH_ERROR = "EXIT_WITH_ERROR"
    COMPLETED = "COMPLETED"


class WeaviateData(Base):
    """
    WeaviateData model for storing training data metadata and processing details.
    
    This model tracks all training data loaded into Weaviate, including metadata
    about the content, processing statistics, and status.
    
    Attributes:
        id (int): Primary key, unique identifier for each training data record.
        collection_name (str): Name of the Weaviate collection where data is stored.
        description (str): Description of the training data content.
        content (text): The original training data content.
        status (str): Current status of the data (e.g., 'processing', 'completed', 'failed').
        no_of_lines (int): Number of lines in the original content.
        no_of_tokens (int): Number of tokens in the content.
        no_of_characters (int): Number of characters in the content.
        data_details (json): JSON object containing additional details like doc_id, chunks_created, etc.
        created_by (int): Foreign key to the user who created this record.
        start_time (datetime): Timestamp when processing started.
        end_time (datetime): Timestamp when processing completed.
        processing_duration (int): Processing duration in seconds.
        created_at (datetime): Timestamp when the record was created.
        deleted_at (datetime): Timestamp when the record was soft deleted (nullable).
        error_msg (str): Error message if processing failed (nullable).
    """
    __tablename__ = "weaviate_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    collection_name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    status = Column(Enum(WeaviateDataStatusEnum), nullable=False, default=WeaviateDataStatusEnum.IN_PROGRESS, index=True)
    no_of_lines = Column(Integer, nullable=True)
    no_of_tokens = Column(Integer, nullable=True)
    no_of_characters = Column(Integer, nullable=True)
    data_details = Column(JSON, nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    processing_duration = Column(Integer, nullable=True)  # Duration in seconds
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_on = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    error_msg = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<WeaviateData(id={self.id}, collection='{self.collection_name}', status='{self.status}')>"
    
    def to_dict(self):
        """Convert WeaviateData object to dictionary."""
        return {
            "id": self.id,
            "collection_name": self.collection_name,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, WeaviateDataStatusEnum) else self.status,
            "no_of_lines": self.no_of_lines,
            "no_of_tokens": self.no_of_tokens,
            "no_of_characters": self.no_of_characters,
            "data_details": self.data_details,
            "created_by": self.created_by,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "processing_duration": self.processing_duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "error_msg": self.error_msg,
            "updated_on": self.updated_on.isoformat() if self.updated_on else None
        }
    
    def calculate_duration(self):
        """Calculate and store processing duration in seconds."""
        if self.start_time and self.end_time:
            self.processing_duration = int((self.end_time - self.start_time).total_seconds())
    
    @property
    def duration_formatted(self):
        """Get formatted processing duration as string."""
        if self.processing_duration is None:
            return None
        
        hours, remainder = divmod(self.processing_duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    @property
    def is_completed(self):
        """Check if processing is completed."""
        return self.status == WeaviateDataStatusEnum.COMPLETED
    
    @property
    def is_failed(self):
        """Check if processing failed."""
        return self.status == WeaviateDataStatusEnum.EXIT_WITH_ERROR
    
    @property
    def is_processing(self):
        """Check if currently processing."""
        return self.status == WeaviateDataStatusEnum.IN_PROGRESS
    
    @property
    def is_cancelled(self):
        """Check if processing was cancelled."""
        return self.status == WeaviateDataStatusEnum.CANCELLED
