from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLAlchemyEnum, func
from sqlalchemy.orm import relationship
from models.base import Base
import enum


class ChatRoleEnum(enum.Enum):
    """Enum for chat message roles."""
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ChatTypeEnum(enum.Enum):
    """Enum for chat content types."""
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    MULTIMODAL = "MULTIMODAL"


class FreeFormChat(Base):
    """
    FreeFormChat model for storing individual chat messages.

    Attributes:
        id (int): Primary key
        project_id (int): Foreign key referencing the freeform project
        role (ChatRoleEnum): Role of the message sender (USER/ASSISTANT/SYSTEM)
        content (str): The message content
        content_type (ChatTypeEnum): Type of content (TEXT/IMAGE/MULTIMODAL)
        attachments (str): JSON string of attachment metadata (nullable)
        created_on (datetime): Timestamp when the message was created
        deleted_on (datetime): Timestamp when the message was deleted (nullable)
    """
    __tablename__ = "freeform_chat"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    project_id = Column(Integer, ForeignKey("freeform_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(SQLAlchemyEnum(ChatRoleEnum), nullable=False, default=ChatRoleEnum.USER)
    content = Column(Text, nullable=True)
    content_type = Column(SQLAlchemyEnum(ChatTypeEnum), nullable=False, default=ChatTypeEnum.TEXT)
    attachments = Column(Text, nullable=True)  # JSON string for image URLs, file paths, etc.
    created_on = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    project = relationship("FreeFormProject", back_populates="chats")

    def __repr__(self):
        return f"<FreeFormChat(id={self.id}, project_id={self.project_id}, role={self.role.value})>"

    def to_dict(self):
        """Convert chat message to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "role": self.role.value if self.role else None,
            "content": self.content,
            "content_type": self.content_type.value if self.content_type else None,
            "attachments": self.attachments,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None
        }
