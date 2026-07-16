from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLAlchemyEnum, func
from sqlalchemy.orm import relationship
import enum

from models.base import Base


class WPPublishStatusEnum(enum.Enum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    UNPUBLISHED = "UNPUBLISHED"
    UPDATED = "UPDATED"


class WordPressPublishLog(Base):
    """
    Tracks every publish/update/unpublish action from Lottie to WordPress.
    One content_id can have multiple log entries (full audit trail).
    """
    __tablename__ = "wordpress_publish_log"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    content_id = Column(Integer, ForeignKey("content.id"), nullable=False)
    wp_post_id = Column(Integer, nullable=True)
    wp_post_url = Column(Text, nullable=True)
    wp_post_type = Column(String(100), nullable=True)
    publish_status = Column(
        SQLAlchemyEnum(WPPublishStatusEnum),
        nullable=False,
        default=WPPublishStatusEnum.PENDING
    )
    published_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    wp_response = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_on = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_on = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    content = relationship("Content", backref="wordpress_logs")
    published_by_user = relationship("User", backref="wordpress_published")

    def __repr__(self):
        return f"<WordPressPublishLog(id={self.id}, content_id={self.content_id}, status={self.publish_status.value}, wp_post_id={self.wp_post_id})>"

    def to_dict(self):
        return {
            "id": self.id,
            "content_id": self.content_id,
            "wp_post_id": self.wp_post_id,
            "wp_post_url": self.wp_post_url,
            "wp_post_type": self.wp_post_type,
            "publish_status": self.publish_status.value if self.publish_status else None,
            "published_by": self.published_by,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "error_message": self.error_message,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "updated_on": self.updated_on.isoformat() if self.updated_on else None,
        }
