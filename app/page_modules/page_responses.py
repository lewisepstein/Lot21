from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PageCreateRequest(BaseModel):
    """
    Request model for creating a new page.
    """
    page_name: str = Field(..., min_length=1, max_length=255, description="Name of the page")
    category_id: Optional[int] = Field(default=None, description="ID of the category (nullable)")
    is_active: bool = Field(default=True, description="Flag indicating if the page is active")


class PageResponse(BaseModel):
    """
    Response model for page operations.
    """
    id: int
    page_name: str
    category_id: Optional[int]
    created_by: Optional[int]
    is_active: bool
    created_on: datetime
    deleted_on: Optional[datetime]
    updated_on: Optional[datetime]

    class Config:
        from_attributes = True


class PageCreateResponse(BaseModel):
    """
    Response model for page creation.
    """
    message: str
    page: PageResponse
