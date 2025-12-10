from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class CategoryAddValidation(BaseModel):
    """
    Pydantic validation model for adding a new category.
    """
    category_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the category"
    )
    is_parent: bool = Field(
        default=False,
        description="Flag indicating if this category is a parent category"
    )
    parent_id: Optional[int] = Field(
        default=None,
        description="ID of the parent category (null for root categories)"
    )
    is_root: bool = Field(
        default=False,
        description="Flag indicating if this category is a root category"
    )
    is_active: bool = Field(
        default=True,
        description="Flag indicating if the category is active"
    )

    @field_validator("category_name")
    @classmethod
    def validate_category_name(cls, v: str) -> str:
        """Validate that category name is not empty or only whitespace."""
        if not v or not v.strip():
            raise ValueError("Category name cannot be empty or only whitespace")
        return v.strip()

    @field_validator("parent_id")
    @classmethod
    def validate_parent_id(cls, v: Optional[int]) -> Optional[int]:
        """Validate that parent_id is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Parent ID must be a positive integer")
        return v

    @field_validator("is_root")
    @classmethod
    def validate_is_root(cls, v: bool, info) -> bool:
        """Validate that root categories don't have parent_id."""
        # Access other fields through info.data
        parent_id = info.data.get("parent_id")
        if v is True and parent_id is not None:
            raise ValueError("Root categories cannot have a parent_id")
        return v


class CategoryUpdateValidation(BaseModel):
    """
    Pydantic validation model for updating an existing category.
    All fields are optional for partial updates.
    """
    category_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Name of the category"
    )
    is_parent: Optional[bool] = Field(
        default=None,
        description="Flag indicating if this category is a parent category"
    )
    parent_id: Optional[int] = Field(
        default=None,
        description="ID of the parent category"
    )
    is_root: Optional[bool] = Field(
        default=None,
        description="Flag indicating if this category is a root category"
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Flag indicating if the category is active"
    )

    @field_validator("category_name")
    @classmethod
    def validate_category_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate that category name is not empty or only whitespace if provided."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError("Category name cannot be empty or only whitespace")
            return v.strip()
        return v

    @field_validator("parent_id")
    @classmethod
    def validate_parent_id(cls, v: Optional[int]) -> Optional[int]:
        """Validate that parent_id is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Parent ID must be a positive integer")
        return v


class CategoryDeleteValidation(BaseModel):
    """
    Pydantic validation model for deleting a category.
    """
    id: int = Field(
        ...,
        gt=0,
        description="ID of the category to delete"
    )
    soft_delete: bool = Field(
        default=True,
        description="Flag indicating whether to soft delete (set deleted_on) or hard delete"
    )


class CategoryResponseValidation(BaseModel):
    """
    Pydantic validation model for category response.
    """
    id: int
    category_name: str
    is_parent: bool
    parent_id: Optional[int]
    is_root: bool
    is_active: bool
    created_on: datetime
    deleted_on: Optional[datetime]

    class Config:
        from_attributes = True  # Allows creation from ORM objects
