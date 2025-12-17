from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PageCreateRequest(BaseModel):
    """
    Request model for creating a new page.
    """
    page_name: str = Field(..., min_length=1, max_length=255, description="Name of the page")
    category_id: Optional[int] = Field(default=None, description="ID of the category (nullable)")
    description: Optional[str] = Field(default=None, description="Description of the page")
    is_active: bool = Field(default=True, description="Flag indicating if the page is active")
    content: Optional[str] = Field(default=None, description="Optional content for the page")
    source_url: Optional[str] = Field(default=None, max_length=200, description="Source URL for the page")
    scrape_data: bool = Field(default=False, description="Flag indicating if data should be scraped from URL")


class PageResponse(BaseModel):
    """
    Response model for page operations.
    """
    id: int
    page_name: str
    category_id: Optional[int]
    description: Optional[str]
    created_by: Optional[int]
    is_active: bool
    source_url: Optional[str]
    scrape_data: bool
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
