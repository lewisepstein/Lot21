"""
Sessions model for user authentication sessions.
Tracks active user sessions for authentication and security.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from models.base import Base


class Session(Base):
    """
    Session model for tracking user authentication sessions.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        session_token: Unique session identifier
        jwt_token: Associated JWT token (hashed for security)
        ip_address: IP address of the session
        user_agent: Browser/client user agent string
        is_active: Whether session is currently active
        expires_at: Session expiration timestamp
        created_at: Session creation timestamp
        last_activity: Last activity timestamp
    """
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    jwt_token_hash = Column(String(255), nullable=True)  # Hashed JWT for security
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, session_token='{self.session_token[:10]}...', is_active={self.is_active})>"
    
    def to_dict(self):
        """Convert session to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_token": self.session_token,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None
        }
