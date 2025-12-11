from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base

class Task(Base):
    """
    SQLAlchemy model for tasks table.
    
    Represents tasks that are associated with schedulers and created by users.
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    task_name = Column(String(255), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_message = Column(Text, nullable=True)
    scheduler_id = Column(Integer, ForeignKey("schedulers.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_on = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator = relationship("User", backref="tasks")
    scheduler = relationship("Scheduler", backref="tasks")

    def __repr__(self):
        return f"<Task(id={self.id}, task_name='{self.task_name}', scheduler_id={self.scheduler_id}, is_active={self.is_active})>"

    def to_dict(self):
        """Convert the task object to a dictionary for API responses."""
        return {
            "id": self.id,
            "task_name": self.task_name,
            "created_by": self.created_by,
            "task_message": self.task_message,
            "scheduler_id": self.scheduler_id,
            "is_active": self.is_active,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None
        }
