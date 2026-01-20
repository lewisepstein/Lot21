from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime
from models.content import ContentActionEnum, ContentApprovalStatusEnum


class ContentAddValidation(BaseModel):
    """
    Pydantic validation model for adding new content.
    """
    category_id: Optional[int] = Field(
        default=None,
        description="ID of the category for this content"
    )
    prompt_data: Optional[str] = Field(
        default=None,
        description="Input prompt data used to generate the content"
    )
    action: Optional[ContentActionEnum] = Field(
        default=None,
        description="Action to perform on the content"
    )

    @field_validator("prompt_data")
    @classmethod
    def validate_prompt_data(cls, v: Optional[str]) -> Optional[str]:
        """Trim and validate prompt data if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class ContentUpdateValidation(BaseModel):
    """
    Pydantic validation model for updating existing content.
    All fields are optional for partial updates.
    """
    task_run_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID of the task run associated with this content"
    )
    category_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID of the category for this content"
    )
    prompt_data: Optional[str] = Field(
        default=None,
        description="Input prompt data used to generate the content"
    )
    generated_content: Optional[str] = Field(
        default=None,
        description="AI-generated content output"
    )
    action: Optional[ContentActionEnum] = Field(
        default=None,
        description="Action to perform on the content"
    )
    approval_status: Optional[ContentApprovalStatusEnum] = Field(
        default=None,
        description="Approval status of the content"
    )
    approval_status_date: Optional[datetime] = Field(
        default=None,
        description="Date when approval status was last updated"
    )
    accuracy: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Accuracy score of the generated content (0-1)"
    )
    comments: Optional[str] = Field(
        default=None,
        description="Comments or feedback about the content"
    )
    quarter: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Quarter identifier (e.g., Q1 2025)"
    )

    @field_validator("prompt_data")
    @classmethod
    def validate_prompt_data(cls, v: Optional[str]) -> Optional[str]:
        """Trim prompt data if provided."""
        if v is not None:
            return v.strip() if v.strip() else None
        return v

    @field_validator("generated_content")
    @classmethod
    def validate_generated_content(cls, v: Optional[str]) -> Optional[str]:
        """Trim generated content if provided."""
        if v is not None:
            return v.strip() if v.strip() else None
        return v

    @field_validator("comments")
    @classmethod
    def validate_comments(cls, v: Optional[str]) -> Optional[str]:
        """Trim comments if provided."""
        if v is not None:
            return v.strip() if v.strip() else None
        return v

    @field_validator("quarter")
    @classmethod
    def validate_quarter(cls, v: Optional[str]) -> Optional[str]:
        """Trim and validate quarter format if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            return v
        return v


class ContentDeleteValidation(BaseModel):
    """
    Pydantic validation model for deleting content.
    """
    id: int = Field(
        ...,
        gt=0,
        description="ID of the content to delete"
    )
    soft_delete: bool = Field(
        default=True,
        description="Flag indicating whether to soft delete (set deleted_on) or hard delete"
    )


class ContentResponseValidation(BaseModel):
    """
    Pydantic validation model for content response.
    """
    id: int
    task_run_id: int
    category_id: int
    prompt_data: Optional[str]
    generated_content: Optional[str]
    created_on: datetime
    deleted_on: Optional[datetime]
    action: str
    approval_status: str
    approval_status_date: Optional[datetime]
    accuracy: Optional[float]
    comments: Optional[str]
    quarter: Optional[str]

    # Pydantic v2 model config
    model_config = ConfigDict(from_attributes=True)  # Allows creation from ORM objects
