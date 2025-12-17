from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base

class Page(Base):
    """
    Page model for database table.
    
    Attributes:
        id (int): Primary key, unique identifier for each page.
        page_name (str): Name of the page.
        category_id (int): Foreign key referencing the category (nullable).
        description (str): Description of the page (nullable).
        source_url (str): Optional source URL for the page (nullable).
        scrape_data (bool): Flag indicating if data should be scraped from the source URL.
        is_active (bool): Flag indicating if the page is active.
        created_by (int): Foreign key referencing the user who created the page (nullable).
        created_on (datetime): Timestamp when the page was created.
        deleted_on (datetime): Timestamp when the page was deleted (nullable).
    """
    __tablename__ = "pages"
    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    page_name = Column(String(255), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    source_url = Column(String(200), nullable=True)
    scrape_data = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_on = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)
    updated_on = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Self-referential relationship for parent-child hierarchy
    parent = relationship("Page", remote_side=[id], backref="children")
    
    def __repr__(self):
        return f"<Page(id={self.id}, name='{self.page_name}', is_root={self.is_root}, parent_id={self.parent_id})>"
    
    def to_dict(self):
        """Convert page object to dictionary."""
        return {
            "id": self.id,
            "page_name": self.page_name,
            "category_id": self.category_id,
            "description": self.description,
            "is_active": self.is_active,
            "source_url": self.source_url,
            "scrape_data": self.scrape_data,
            "created_by": self.created_by,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None,
            "updated_on": self.updated_on.isoformat() if self.updated_on else None
        }
    