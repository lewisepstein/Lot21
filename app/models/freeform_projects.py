from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import relationship
from models.base import Base


class FreeFormProject(Base):
    """
    FreeFormProject model for managing AI chat projects/sessions.

    Attributes:
        id (int): Primary key
        project_name (str): Name of the project
        project_description (str): Description of the project (nullable)
        created_by (int): Foreign key referencing the user who created the project
        created_on (datetime): Timestamp when the project was created
        updated_on (datetime): Timestamp when the project was last updated
        deleted_on (datetime): Timestamp when the project was deleted (nullable)
        is_active (bool): Flag indicating if the project is active
    """
    __tablename__ = "freeform_projects"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    project_name = Column(String(255), nullable=False, index=True)
    project_description = Column(String(500), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_on = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_on = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    deleted_on = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    created_by_user = relationship("User", backref="freeform_projects")
    chats = relationship("FreeFormChat", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FreeFormProject(id={self.id}, name='{self.project_name}', created_by={self.created_by})>"

    def to_dict(self):
        """Convert project object to dictionary."""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "project_description": self.project_description,
            "created_by": self.created_by,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "updated_on": self.updated_on.isoformat() if self.updated_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None,
            "is_active": self.is_active
        }
