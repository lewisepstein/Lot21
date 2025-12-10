from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class TaskAddValidation(BaseModel):
    """
    Pydantic validation model for adding a new task.
    """
    task_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the task"
    )
    created_by: int = Field(
        ...,
        gt=0,
        description="ID of the user creating the task"
    )
    task_message: Optional[str] = Field(
        default=None,
        description="Optional message or description for the task"
    )
    scheduler_id: int = Field(
        ...,
        gt=0,
        description="ID of the scheduler associated with this task"
    )
    is_active: bool = Field(
        default=True,
        description="Flag indicating if the task is active"
    )

    @field_validator("task_name")
    @classmethod
    def validate_task_name(cls, v: str) -> str:
        """Validate that task name is not empty or only whitespace."""
        if not v or not v.strip():
            raise ValueError("Task name cannot be empty or only whitespace")
        return v.strip()

    @field_validator("task_message")
    @classmethod
    def validate_task_message(cls, v: Optional[str]) -> Optional[str]:
        """Trim task message if provided."""
        if v is not None:
            return v.strip() if v.strip() else None
        return v


class TaskUpdateValidation(BaseModel):
    """
    Pydantic validation model for updating an existing task.
    All fields are optional for partial updates.
    """
    task_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Name of the task"
    )
    task_message: Optional[str] = Field(
        default=None,
        description="Message or description for the task"
    )
    scheduler_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID of the scheduler associated with this task"
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Flag indicating if the task is active"
    )

    @field_validator("task_name")
    @classmethod
    def validate_task_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate that task name is not empty or only whitespace if provided."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError("Task name cannot be empty or only whitespace")
            return v.strip()
        return v

    @field_validator("task_message")
    @classmethod
    def validate_task_message(cls, v: Optional[str]) -> Optional[str]:
        """Trim task message if provided."""
        if v is not None:
            return v.strip() if v.strip() else None
        return v


class TaskDeleteValidation(BaseModel):
    """
    Pydantic validation model for deleting a task.
    """
    id: int = Field(
        ...,
        gt=0,
        description="ID of the task to delete"
    )
    soft_delete: bool = Field(
        default=True,
        description="Flag indicating whether to soft delete (set deleted_on) or hard delete"
    )


class TaskResponseValidation(BaseModel):
    """
    Pydantic validation model for task response.
    """
    id: int
    task_name: str
    created_by: int
    task_message: Optional[str]
    scheduler_id: int
    is_active: bool
    created_on: datetime
    deleted_on: Optional[datetime]

    class Config:
        from_attributes = True  # Allows creation from ORM objects
