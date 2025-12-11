from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLAlchemyEnum, func
from sqlalchemy.orm import relationship
import enum
import uuid as uuid_lib
from models.base import Base


class TaskRunStatusEnum(enum.Enum):
    """
    Enum for task run status values.
    """
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
    task_run_status = Column(SQLAlchemyEnum(TaskRunStatusEnum), nullable=False, default=TaskRunStatusEnum.IN_PROGRESS)
    task_run_message = Column(Text, nullable=True)
    created_on = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)
    scheduled_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)

    # Relationship
    task = relationship("Task", backref="task_runs")

    def __repr__(self):
        return f"<TaskRun(id={self.id}, uuid='{self.uuid}', status={self.task_run_status.value}, scheduled_task_id={self.scheduled_task_id}, content_id={self.content_id})>"

    def to_dict(self):
        """Convert the task run object to a dictionary for API responses."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "task_run_status": self.task_run_status.value if self.task_run_status else None,
            "task_run_message": self.task_run_message,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None,
            "scheduled_task_id": self.scheduled_task_id,
        }


class ProcessStatusEnum(enum.Enum):
    """
    Enum for process status values.
    """
    RUNNING = "RUNNING"
    STALLED = "STALLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"
    CRASHED = "CRASHED"


class TaskProcess(Base):
    """
    SQLAlchemy model for task_processes table.
    
    Represents processes associated with task runs.
    """
    __tablename__ = "task_bg_processes"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    task_run_id = Column(Integer, ForeignKey("task_runs.id"), nullable=False)
    process_id = Column(Integer, nullable=False)
    created_on = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    cpu_usage = Column(Integer, nullable=True)
    memory_usage = Column(Integer, nullable=True)
    process_status = Column(SQLAlchemyEnum(ProcessStatusEnum), nullable=False, default=ProcessStatusEnum.RUNNING)

    # Relationship
    task_run = relationship("TaskRun", backref="task_bg_processes")

    def __repr__(self):
        return f"<TaskProcess(id={self.id}, task_run_id={self.task_run_id}, process_id={self.process_id})>"

    def to_dict(self):
        """Convert the task process object to a dictionary for API responses."""
        return {
            "id": self.id,
            "task_run_id": self.task_run_id,
            "process_id": self.process_id,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "process_status": self.process_status.value if self.process_status else None,
        }