from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from models.base import Base

class Category(Base):
    """
    Category model for database table.
    
    Attributes:
        id (int): Primary key, unique identifier for each category.
        category_name (str): Name of the category.
        is_parent (bool): Flag indicating if this category is a parent category.
        parent_id (int): Foreign key referencing the parent category (nullable).
        is_root (bool): Flag indicating if this category is a root category.
        is_active (bool): Flag indicating if the category is active.
        created_on (datetime): Timestamp when the category was created.
        deleted_on (datetime): Timestamp when the category was deleted (nullable).
    """
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    category_name = Column(String(255), nullable=False, index=True)
    is_parent = Column(Boolean, default=False, nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_root = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_on = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)
    
    # Self-referential relationship for parent-child hierarchy
    parent = relationship("Category", remote_side=[id], backref="children")
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.category_name}', is_root={self.is_root}, parent_id={self.parent_id})>"
    
    def to_dict(self):
        """Convert category object to dictionary."""
        return {
            "id": self.id,
            "category_name": self.category_name,
            "is_parent": self.is_parent,
            "parent_id": self.parent_id,
            "is_root": self.is_root,
            "is_active": self.is_active,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None
        }
