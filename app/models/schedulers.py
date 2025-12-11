from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base

class Scheduler(Base):
    """
    SQLAlchemy model for schedulers table.
    
    Represents scheduled tasks or jobs in the system.
    """
    __tablename__ = "schedulers"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    scheduler_name = Column(String(255), nullable=False, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_on = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_on = Column(DateTime(timezone=True), nullable=True)

    # Relationship to User model
    creator = relationship("User", backref="schedulers")

    def __repr__(self):
        return f"<Scheduler(id={self.id}, scheduler_name='{self.scheduler_name}', scheduled_at={self.scheduled_at}, is_active={self.is_active})>"

    def to_dict(self):
        """Convert the scheduler object to a dictionary for API responses."""
        return {
            "id": self.id,
            "scheduler_name": self.scheduler_name,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "deleted_on": self.deleted_on.isoformat() if self.deleted_on else None
        }
