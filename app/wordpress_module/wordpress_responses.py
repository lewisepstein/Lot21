from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class PublishResponse(BaseModel):
    success: bool
    message: str
    content_id: int
    wp_post_id: Optional[int] = None
    wp_post_url: Optional[str] = None
    publish_status: Optional[str] = None


class UnpublishResponse(BaseModel):
    success: bool
    message: str
    content_id: int
    wp_post_id: Optional[int] = None


class PublishStatusResponse(BaseModel):
    content_id: int
    publish_status: Optional[str] = None
    wp_post_id: Optional[int] = None
    wp_post_url: Optional[str] = None
    wp_post_type: Optional[str] = None
    published_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    error_message: Optional[str] = None
    never_published: bool = False


class PublishedItemResponse(BaseModel):
    log_id: int
    content_id: int
    wp_post_id: Optional[int] = None
    wp_post_url: Optional[str] = None
    wp_post_type: Optional[str] = None
    publish_status: str
    published_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None


class PublishedListResponse(BaseModel):
    total: int
    items: List[PublishedItemResponse]


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    site_url: str
