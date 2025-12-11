from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from models.base import Base



class ContentActionEnum(enum.Enum):
    """
    Enum for content action values.
    """
    DRAFT = "DRAFT"
    RE_RUN = "RE_RUN"
    CANCEL = "CANCEL"
    STOP = "STOP"


class ContentApprovalStatusEnum(enum.Enum):
    """
    Enum for content approval status values.
    """
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_NEEDED = "REVISION_NEEDED"


class Content(Base):
    """
    SQLAlchemy model for content table.
    
    Represents generated content with approval workflow and accuracy tracking.
    """
    __tablename__ = "content"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    task_run_id = Column(Integer, ForeignKey("task_runs.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    prompt_data = Column(Text, nullable=True)
    generated_content = Column(Text, nullable=True)
    created_on = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)
    action = Column(SQLAlchemyEnum(ContentActionEnum), nullable=False, default=ContentActionEnum.DRAFT)
    approval_status = Column(SQLAlchemyEnum(ContentApprovalStatusEnum), nullable=False, default=ContentApprovalStatusEnum.PENDING)
    approval_status_date = Column(DateTime(timezone=True), nullable=True)
    accuracy = Column(Float, nullable=True)
    comments = Column(Text, nullable=True)
    quarter = Column(String(50), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    task_run = relationship("TaskRun", backref="contents")
    category = relationship("Category", backref="contents")
    created_by_user = relationship("User", backref="contents_created")
    def __repr__(self):
        return f"<Content(id={self.id}, task_run_id={self.task_run_id}, category_id={self.category_id}, approval_status={self.approval_status.value})>"

    def to_dict(self):
        """Convert the content object to a dictionary for API responses."""
        return {
            "id": self.id,
            "task_run_id": self.task_run_id,
            "category_id": self.category_id,
            "prompt_data": self.prompt_data,
            "generated_content": self.generated_content,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None,
            "action": self.action.value if self.action else None,
            "approval_status": self.approval_status.value if self.approval_status else None,
            "approval_status_date": self.approval_status_date.isoformat() if self.approval_status_date else None,
            "accuracy": self.accuracy,
            "comments": self.comments,
            "quarter": self.quarter
        }
