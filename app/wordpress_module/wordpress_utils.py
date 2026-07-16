"""
Database utility functions for the wordpress_publish_log table.
All DB operations for tracking publish/update/unpublish history.
"""
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from service_utils.db_utils.pg_db import PostgresDB
from models.wordpress_publish import WPPublishStatusEnum
from service_utils.log_management import get_logger

logger = get_logger(__name__)


def get_publish_log_by_content(content_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the most recent publish log for a content_id.
    Returns None if this content has never been published.
    """
    db = PostgresDB()
    results = db.read(
        "wordpress_publish_log",
        conditions={"content_id": content_id},
        order_by=[("created_on", False)],
        limit=1
    )
    return results[0] if results else None


def get_published_log(content_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the active PUBLISHED log entry for a content_id.
    Returns None if content is not currently published.
    """
    db = PostgresDB()
    results = db.read(
        "wordpress_publish_log",
        conditions={
            "content_id": content_id,
            "publish_status": WPPublishStatusEnum.PUBLISHED.value
        },
        order_by=[("created_on", False)],
        limit=1
    )
    return results[0] if results else None


def create_publish_log(
    content_id: int,
    wp_post_type: str,
    published_by: int,
    wp_post_id: Optional[int] = None,
    wp_post_url: Optional[str] = None,
    publish_status: WPPublishStatusEnum = WPPublishStatusEnum.PENDING,
    wp_response: Optional[Dict] = None,
    error_message: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Create a new wordpress_publish_log record."""
    db = PostgresDB()

    record = {
        "content_id": content_id,
        "wp_post_id": wp_post_id,
        "wp_post_url": wp_post_url,
        "wp_post_type": wp_post_type,
        "publish_status": publish_status.value,
        "published_by": published_by,
        "published_at": datetime.now(timezone.utc) if publish_status == WPPublishStatusEnum.PUBLISHED else None,
        "wp_response": json.dumps(wp_response) if wp_response else None,
        "error_message": error_message,
    }

    result = db.create("wordpress_publish_log", record)
    if not result:
        logger.error(f"wordpress_utils: failed to create publish log for content_id={content_id}")
    return result


def update_publish_log(
    log_id: int,
    publish_status: WPPublishStatusEnum,
    wp_post_id: Optional[int] = None,
    wp_post_url: Optional[str] = None,
    wp_response: Optional[Dict] = None,
    error_message: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update an existing publish log record after WP API responds."""
    db = PostgresDB()

    updates: Dict[str, Any] = {
        "publish_status": publish_status.value,
        "last_synced_at": datetime.now(timezone.utc),
    }

    if wp_post_id is not None:
        updates["wp_post_id"] = wp_post_id
    if wp_post_url is not None:
        updates["wp_post_url"] = wp_post_url
    if wp_response is not None:
        updates["wp_response"] = json.dumps(wp_response)
    if error_message is not None:
        updates["error_message"] = error_message
    if publish_status == WPPublishStatusEnum.PUBLISHED:
        updates["published_at"] = datetime.now(timezone.utc)

    return db.update("wordpress_publish_log", conditions={"id": log_id}, data=updates)


def get_all_published(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """List all currently published content with their live WP URLs."""
    db = PostgresDB()
    results = db.read(
        "wordpress_publish_log",
        conditions={"publish_status": WPPublishStatusEnum.PUBLISHED.value},
        order_by=[("published_at", False)],
        limit=limit
    )
    return results or []


def content_is_already_published(content_id: int) -> bool:
    """Check if a content item already has an active PUBLISHED log."""
    return get_published_log(content_id) is not None
