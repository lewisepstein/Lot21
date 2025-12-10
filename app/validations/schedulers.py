from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class SchedulerAddValidation(BaseModel):
    """
    Pydantic validation model for adding a new scheduler.
    """
    scheduler_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the scheduler"
    )
    scheduled_at: datetime = Field(
        ...,
        description="Date and time when the scheduler should run"
    )
    is_active: bool = Field(
        default=True,
        description="Flag indicating if the scheduler is active"
    )
    created_by: int = Field(
        ...,
        gt=0,
        description="ID of the user creating the scheduler"
    )

    @field_validator("scheduler_name")
    @classmethod
    def validate_scheduler_name(cls, v: str) -> str:
        """Validate that scheduler name is not empty or only whitespace."""
        if not v or not v.strip():
            raise ValueError("Scheduler name cannot be empty or only whitespace")
        return v.strip()

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, v: datetime) -> datetime:
        """Validate that scheduled_at is not in the past."""
        if v < datetime.now(v.tzinfo or datetime.now().astimezone().tzinfo):
            raise ValueError("Scheduled time cannot be in the past")
        return v


class SchedulerUpdateValidation(BaseModel):
    """
    Pydantic validation model for updating an existing scheduler.
    All fields are optional for partial updates.
    """
    scheduler_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Name of the scheduler"
    )
    scheduled_at: Optional[datetime] = Field(
        default=None,
        description="Date and time when the scheduler should run"
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Flag indicating if the scheduler is active"
    )

    @field_validator("scheduler_name")
    @classmethod
    def validate_scheduler_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate that scheduler name is not empty or only whitespace if provided."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError("Scheduler name cannot be empty or only whitespace")
            return v.strip()
        return v

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate that scheduled_at is not in the past if provided."""
        if v is not None:
            if v < datetime.now(v.tzinfo or datetime.now().astimezone().tzinfo):
                raise ValueError("Scheduled time cannot be in the past")
        return v


class SchedulerDeleteValidation(BaseModel):
    """
    Pydantic validation model for deleting a scheduler.
    """
    id: int = Field(
        ...,
        gt=0,
        description="ID of the scheduler to delete"
    )
    soft_delete: bool = Field(
        default=True,
        description="Flag indicating whether to soft delete (set deleted_on) or hard delete"
    )


class SchedulerResponseValidation(BaseModel):
    """
    Pydantic validation model for scheduler response.
    """
    id: int
    scheduler_name: str
    scheduled_at: datetime
    is_active: bool
    created_by: int
    created_on: datetime
    deleted_on: Optional[datetime]

    class Config:
        from_attributes = True  # Allows creation from ORM objects
