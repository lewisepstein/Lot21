"""
WordPress publishing routes.
All endpoints require Bearer token authentication.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth_module.auth_utils import verify_token
from service_utils.db_utils.pg_db import PostgresDB
from service_utils.log_management import get_logger
from models.wordpress_publish import WPPublishStatusEnum
from models.content import ContentApprovalStatusEnum

from wordpress_module import wordpress_client
from wordpress_module import content_mapper
from wordpress_module import wordpress_utils
from wordpress_module.wordpress_responses import (
    PublishResponse,
    UnpublishResponse,
    PublishStatusResponse,
    PublishedListResponse,
    PublishedItemResponse,
    ConnectionTestResponse,
)
from wordpress_module.wp_config import WP_SITE_URL, validate_wp_config

logger = get_logger(__name__)
router = APIRouter(prefix="/user/wordpress", tags=["wordpress"])
security = HTTPBearer()


def _get_verified_user(credentials: HTTPAuthorizationCredentials) -> dict:
    token_data = verify_token(credentials.credentials)
    if not token_data:
        raise HTTPException(status_code=401, detail="Authentication failed")
    return token_data


def _get_content_record(content_id: int) -> dict:
    db = PostgresDB()
    results = db.read("content", conditions={"id": content_id, "deleted_on": None}, limit=1)
    if not results:
        raise HTTPException(status_code=404, detail=f"Content ID {content_id} not found")
    return results[0]


# ---------------------------------------------------------------------------
# POST /user/wordpress/publish/{content_id}
# ---------------------------------------------------------------------------
@router.post("/publish/{content_id}", response_model=PublishResponse)
async def publish_content(
    content_id: int,
    taxonomy_term: Optional[str] = Query(default=None, description="e.g. Adapt, Mitigate, National"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Publish an APPROVED content item to the live WordPress website.
    If it was previously published, this updates the existing WP post.
    """
    token_data = _get_verified_user(credentials)
    user_id = token_data.get("user_id")

    if not validate_wp_config():
        raise HTTPException(status_code=503, detail="WordPress credentials not configured. Add WP_SITE_URL, WP_APP_USERNAME, WP_APP_PASSWORD to .env")

    content = _get_content_record(content_id)

    # Guard: only APPROVED content can go live
    if content.get("approval_status") != ContentApprovalStatusEnum.APPROVED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Content must be APPROVED before publishing. Current status: {content.get('approval_status')}"
        )

    content_type = content.get("content_type")
    generated_content = content.get("generated_content") or ""

    # Build the WordPress payload
    success, cpt_slug, payload = content_mapper.build_wp_payload(
        content_type=content_type,
        generated_content=generated_content,
        taxonomy_term=taxonomy_term,
        publish=True
    )

    if not success:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot build WP payload for content_type='{content_type}'. Check wp_field_config.json."
        )

    # Check if already published — update instead of create
    existing_log = wordpress_utils.get_published_log(content_id)

    if existing_log and existing_log.get("wp_post_id"):
        wp_post_id = existing_log["wp_post_id"]
        logger.info(f"Content {content_id} already published as WP post {wp_post_id} — updating")

        log_entry = wordpress_utils.create_publish_log(
            content_id=content_id,
            wp_post_type=cpt_slug,
            published_by=user_id,
            publish_status=WPPublishStatusEnum.PENDING
        )

        ok, result = await wordpress_client.update_post(cpt_slug, wp_post_id, payload)
    else:
        logger.info(f"Publishing content {content_id} as new WP post to /{cpt_slug}")

        log_entry = wordpress_utils.create_publish_log(
            content_id=content_id,
            wp_post_type=cpt_slug,
            published_by=user_id,
            publish_status=WPPublishStatusEnum.PENDING
        )

        ok, result = await wordpress_client.create_post(cpt_slug, payload)

    if not log_entry:
        logger.error(f"Failed to create publish log for content_id={content_id}")

    if ok:
        wordpress_utils.update_publish_log(
            log_id=log_entry["id"],
            publish_status=WPPublishStatusEnum.PUBLISHED,
            wp_post_id=result.get("wp_post_id"),
            wp_post_url=result.get("wp_post_url"),
            wp_response=result.get("raw", {})
        )
        logger.info(f"Published content {content_id} → WP post {result.get('wp_post_id')} at {result.get('wp_post_url')}")
        return PublishResponse(
            success=True,
            message="Content published successfully",
            content_id=content_id,
            wp_post_id=result.get("wp_post_id"),
            wp_post_url=result.get("wp_post_url"),
            publish_status=WPPublishStatusEnum.PUBLISHED.value
        )
    else:
        wordpress_utils.update_publish_log(
            log_id=log_entry["id"],
            publish_status=WPPublishStatusEnum.FAILED,
            error_message=result.get("error", "Unknown error"),
            wp_response=result
        )
        logger.error(f"Failed to publish content {content_id}: {result.get('error')}")
        raise HTTPException(status_code=502, detail=f"WordPress API error: {result.get('error')} — {result.get('detail', '')}")


# ---------------------------------------------------------------------------
# PUT /user/wordpress/unpublish/{content_id}
# ---------------------------------------------------------------------------
@router.put("/unpublish/{content_id}", response_model=UnpublishResponse)
async def unpublish_content(
    content_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Set the WordPress post back to draft. Does not delete the WP post.
    The wp_post_id is preserved so it can be re-published later.
    """
    _get_verified_user(credentials)

    if not validate_wp_config():
        raise HTTPException(status_code=503, detail="WordPress credentials not configured")

    existing_log = wordpress_utils.get_published_log(content_id)
    if not existing_log:
        raise HTTPException(status_code=404, detail=f"Content {content_id} is not currently published")

    wp_post_id = existing_log.get("wp_post_id")
    cpt_slug = existing_log.get("wp_post_type")

    ok, result = await wordpress_client.unpublish_post(cpt_slug, wp_post_id)

    if ok:
        wordpress_utils.update_publish_log(
            log_id=existing_log["id"],
            publish_status=WPPublishStatusEnum.UNPUBLISHED,
            wp_response=result.get("raw", {})
        )
        return UnpublishResponse(
            success=True,
            message="Content set to draft on WordPress",
            content_id=content_id,
            wp_post_id=wp_post_id
        )
    else:
        raise HTTPException(status_code=502, detail=f"WordPress API error: {result.get('error')}")


# ---------------------------------------------------------------------------
# GET /user/wordpress/status/{content_id}
# ---------------------------------------------------------------------------
@router.get("/status/{content_id}", response_model=PublishStatusResponse)
async def publish_status(
    content_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Return the current publish status for a content item."""
    _get_verified_user(credentials)
    _get_content_record(content_id)

    log = wordpress_utils.get_publish_log_by_content(content_id)

    if not log:
        return PublishStatusResponse(content_id=content_id, never_published=True)

    return PublishStatusResponse(
        content_id=content_id,
        publish_status=log.get("publish_status"),
        wp_post_id=log.get("wp_post_id"),
        wp_post_url=log.get("wp_post_url"),
        wp_post_type=log.get("wp_post_type"),
        published_at=log.get("published_at"),
        last_synced_at=log.get("last_synced_at"),
        error_message=log.get("error_message"),
        never_published=False
    )


# ---------------------------------------------------------------------------
# GET /user/wordpress/published
# ---------------------------------------------------------------------------
@router.get("/published", response_model=PublishedListResponse)
async def list_published(
    limit: int = Query(default=50, le=200),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """List all content items that are currently published on WordPress."""
    _get_verified_user(credentials)

    items = wordpress_utils.get_all_published(limit=limit)
    return PublishedListResponse(
        total=len(items),
        items=[
            PublishedItemResponse(
                log_id=item["id"],
                content_id=item["content_id"],
                wp_post_id=item.get("wp_post_id"),
                wp_post_url=item.get("wp_post_url"),
                wp_post_type=item.get("wp_post_type"),
                publish_status=item.get("publish_status", ""),
                published_at=item.get("published_at"),
                last_synced_at=item.get("last_synced_at"),
            )
            for item in items
        ]
    )


# ---------------------------------------------------------------------------
# GET /user/wordpress/test-connection
# ---------------------------------------------------------------------------
@router.get("/test-connection", response_model=ConnectionTestResponse)
async def test_wp_connection(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Verify WordPress API credentials are working. Run this before publishing."""
    _get_verified_user(credentials)

    if not validate_wp_config():
        return ConnectionTestResponse(
            success=False,
            message="WP_SITE_URL, WP_APP_USERNAME or WP_APP_PASSWORD not set in .env",
            site_url=WP_SITE_URL or "not set"
        )

    ok, message = await wordpress_client.test_connection()
    return ConnectionTestResponse(success=ok, message=message, site_url=WP_SITE_URL)
