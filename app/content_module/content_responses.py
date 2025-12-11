from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ContentCreateRequest(BaseModel):
    """
    Request model for creating new content.
    """
    task_run_id: int = Field(..., gt=0, description="ID of the task run")
    category_id: int = Field(..., gt=0, description="ID of the category")
    prompt_data: Optional[str] = Field(default=None, description="Input prompt data")
    generated_content: Optional[str] = Field(default=None, description="AI-generated content")
    action: Optional[str] = Field(default="DRAFT", description="Content action")
    approval_status: Optional[str] = Field(default="PENDING", description="Approval status")
    accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Accuracy score")
    comments: Optional[str] = Field(default=None, description="Comments")
    quarter: Optional[str] = Field(default=None, max_length=50, description="Quarter identifier")


class ContentResponse(BaseModel):
    """
    Response model for content operations.
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

    class Config:
        from_attributes = True


class ContentCreateResponse(BaseModel):
    """
    Response model for content creation.
    """
    message: str
    content: ContentResponse
