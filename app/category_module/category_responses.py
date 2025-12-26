from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class CategoryCreateRequest(BaseModel):
    """
    Request model for creating a new category.
    """
    category_name: str = Field(..., min_length=1, max_length=255, description="Name of the category")
    is_parent: bool = Field(default=False, description="Flag indicating if this category is a parent category")
    parent_id: Optional[int] = Field(default=None, description="ID of the parent category (nullable)")
    is_root: bool = Field(default=False, description="Flag indicating if this category is a root category")
    is_active: bool = Field(default=True, description="Flag indicating if the category is active")


class CategoryResponse(BaseModel):
    """
    Response model for category operations.
    """
    id: int
    category_name: str
    is_parent: bool
    parent_id: Optional[int]
    is_root: bool
    is_active: bool
    created_on: datetime
    deleted_on: Optional[datetime]
    updated_on: Optional[datetime]

    # Pydantic v2 model config
    model_config = ConfigDict(from_attributes=True)


class CategoryCreateResponse(BaseModel):
    """
    Response model for category creation.
    """
    message: str
    category: CategoryResponse
