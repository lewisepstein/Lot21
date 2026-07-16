"""
WordPress credentials loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

WP_SITE_URL = os.getenv("WP_SITE_URL", "").rstrip("/")
WP_APP_USERNAME = os.getenv("WP_APP_USERNAME", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")


def validate_wp_config() -> bool:
    """Returns True if all required WP env vars are set."""
    return all([WP_SITE_URL, WP_APP_USERNAME, WP_APP_PASSWORD])
