"""
WordPress REST API async client.
Handles all HTTP communication with the WordPress site.
Authentication: WordPress Application Passwords (Basic Auth).
"""
import base64
import json
from typing import Optional, Dict, Any, Tuple

import httpx

from service_utils.log_management import get_logger
from wordpress_module.wp_config import WP_SITE_URL, WP_APP_USERNAME, WP_APP_PASSWORD

logger = get_logger(__name__)

TIMEOUT = 30.0


def _auth_header() -> Dict[str, str]:
    """Build the Basic Auth header from WP Application Password credentials."""
    credentials = f"{WP_APP_USERNAME}:{WP_APP_PASSWORD}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
    }


async def test_connection() -> Tuple[bool, str]:
    """
    Test that WP credentials are valid by calling /wp-json/wp/v2/users/me.
    Returns (success: bool, message: str).
    """
    url = f"{WP_SITE_URL}/wp-json/wp/v2/users/me"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url, headers=_auth_header())
        if response.status_code == 200:
            data = response.json()
            return True, f"Connected as: {data.get('name', 'unknown')} (ID: {data.get('id')})"
        return False, f"Auth failed — HTTP {response.status_code}: {response.text[:200]}"
    except httpx.RequestError as e:
        return False, f"Connection error: {str(e)}"


async def create_post(cpt_slug: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Create and publish a new post on WordPress.
    Returns (success: bool, response_data: dict).
    response_data contains 'wp_post_id' and 'wp_post_url' on success,
    or 'error' on failure.
    """
    url = f"{WP_SITE_URL}/wp-json/wp/v2/{cpt_slug}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                url,
                headers=_auth_header(),
                content=json.dumps(payload)
            )

        if response.status_code in (200, 201):
            data = response.json()
            return True, {
                "wp_post_id": data.get("id"),
                "wp_post_url": data.get("link"),
                "raw": data
            }

        return False, {
            "error": f"HTTP {response.status_code}",
            "detail": response.text[:500]
        }

    except httpx.RequestError as e:
        logger.error(f"WP create_post request error: {str(e)}")
        return False, {"error": str(e)}


async def update_post(cpt_slug: str, wp_post_id: int, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Update an existing WordPress post (re-sync content).
    Returns (success: bool, response_data: dict).
    """
    url = f"{WP_SITE_URL}/wp-json/wp/v2/{cpt_slug}/{wp_post_id}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.put(
                url,
                headers=_auth_header(),
                content=json.dumps(payload)
            )

        if response.status_code == 200:
            data = response.json()
            return True, {
                "wp_post_id": data.get("id"),
                "wp_post_url": data.get("link"),
                "raw": data
            }

        return False, {
            "error": f"HTTP {response.status_code}",
            "detail": response.text[:500]
        }

    except httpx.RequestError as e:
        logger.error(f"WP update_post request error: {str(e)}")
        return False, {"error": str(e)}


async def unpublish_post(cpt_slug: str, wp_post_id: int) -> Tuple[bool, Dict[str, Any]]:
    """
    Set a WordPress post back to draft (does not delete it).
    Returns (success: bool, response_data: dict).
    """
    return await update_post(cpt_slug, wp_post_id, {"status": "draft"})


async def get_post(cpt_slug: str, wp_post_id: int) -> Tuple[bool, Dict[str, Any]]:
    """
    Fetch a post from WordPress to check its current status.
    Returns (success: bool, response_data: dict).
    """
    url = f"{WP_SITE_URL}/wp-json/wp/v2/{cpt_slug}/{wp_post_id}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url, headers=_auth_header())

        if response.status_code == 200:
            data = response.json()
            return True, {
                "wp_post_id": data.get("id"),
                "wp_post_url": data.get("link"),
                "status": data.get("status"),
                "title": data.get("title", {}).get("rendered"),
                "modified": data.get("modified")
            }

        return False, {
            "error": f"HTTP {response.status_code}",
            "detail": response.text[:200]
        }

    except httpx.RequestError as e:
        logger.error(f"WP get_post request error: {str(e)}")
        return False, {"error": str(e)}
