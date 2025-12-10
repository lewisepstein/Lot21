from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid as uuid_lib
from models.base import Base


class TaskRunStatusEnum(enum.Enum):
    """
    Enum for task run status values.
    """
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class TaskRun(Base):
    """
    SQLAlchemy model for tasks_runs table.
    
    Represents individual execution runs of tasks with status tracking.
    """
    __tablename__ = "task_runs"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()), index=True)
    task_run_status = Column(SQLAlchemyEnum(TaskRunStatusEnum), nullable=False, default=TaskRunStatusEnum.PENDING)
    task_run_message = Column(Text, nullable=True)
    created_on = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)
    scheduled_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)

    # Relationship
    task = relationship("Task", backref="task_runs")

    def __repr__(self):
        return f"<TaskRun(id={self.id}, uuid='{self.uuid}', status={self.task_run_status.value}, scheduled_task_id={self.scheduled_task_id})>"

    def to_dict(self):
        """Convert the task run object to a dictionary for API responses."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "task_run_status": self.task_run_status.value if self.task_run_status else None,
            "task_run_message": self.task_run_message,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None,
            "scheduled_task_id": self.scheduled_task_id
        }
