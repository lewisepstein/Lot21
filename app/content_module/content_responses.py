from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ContentCreateRequest(BaseModel):
    """
    Request model for creating new content.
    """
    category_id: int = Field(..., gt=0, description="ID of the category")
    prompt_data: Optional[str] = Field(default=None, description="Input prompt data")


class ContentResponse(BaseModel):
    """
    Response model for content operations.
    """
    id: int
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
