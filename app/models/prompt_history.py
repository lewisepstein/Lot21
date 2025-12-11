from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLAlchemyEnum, func
from sqlalchemy.orm import relationship
from models.base import Base
import enum

class PromptTypeEnum(enum.Enum):
    """
    Enum for task run status values.
    """
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    MULTITYPE = "MULTITYPE"

class PromptHistory(Base):
    """
    SQLAlchemy model for prompt_history table.
    
    Represents the history of prompts and AI interactions for content generation.
    """
    __tablename__ = "prompt_history"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    prompt_session_id = Column(String(255), nullable=False, index=True)
    content_id = Column(Integer, ForeignKey("content.id"), nullable=False)
    task_run_id = Column(Integer, ForeignKey("task_runs.id"), nullable=False)
    user_prompt = Column(Text, nullable=True)
    ai_response = Column(Text, nullable=True)
    prompt_type = Column(SQLAlchemyEnum(PromptTypeEnum), nullable=True, default=PromptTypeEnum.TEXT)
    created_on = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    content = relationship("Content", backref="prompt_histories")
    task_run = relationship("TaskRun", backref="prompt_histories")

    def __repr__(self):
        return f"<PromptHistory(id={self.id}, prompt_session_id='{self.prompt_session_id}', content_id={self.content_id}, task_run_id={self.task_run_id})>"

    def to_dict(self):
        """Convert the prompt history object to a dictionary for API responses."""
        return {
            "id": self.id,
            "prompt_session_id": self.prompt_session_id,
            "content_id": self.content_id,
            "task_run_id": self.task_run_id,
            "user_prompt": self.user_prompt,
            "ai_response": self.ai_response,
            "prompt_type": self.prompt_type,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None
        }
