from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime, timezone
from models.base import Base

class User(Base):
    """
    User model for database table.
    
    Attributes:
        id (int): Primary key, unique identifier for each user.
        email (str): User's email address.
        passwd (str): User's hashed password.
        is_active (bool): Flag indicating if the user account is active.
        created_on (datetime): Timestamp when the user was created.
        deleted_on (datetime): Timestamp when the user was deleted (nullable).
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    passwd = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_on = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', is_active={self.is_active})>"
    
    def to_dict(self):
        """Convert user object to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "is_active": self.is_active,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None
        }
    