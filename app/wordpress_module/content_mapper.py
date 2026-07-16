"""
Maps generated content from Lottie DB into a WordPress REST API payload.

Flow:
  content record (DB) → load wp_field_config.json → build WP post payload
  { title, content, status, taxonomy terms, acf fields }

The generated_content field is treated as JSON first.
If it cannot be parsed as JSON, the full text is used as the post body.
"""
import json
import os
from typing import Dict, Any, Optional, Tuple

from service_utils.log_management import get_logger

logger = get_logger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "wp_field_config.json")


def _load_config() -> Dict[str, Any]:
    with open(_CONFIG_PATH, "r") as f:
        return json.load(f)


def _parse_generated_content(raw: str) -> Dict[str, Any]:
    """
    Try to parse generated_content as JSON.
    Falls back to { "body": raw_text } if it is plain text.
    """
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return {"body": raw}


def build_wp_payload(
    content_type: str,
    generated_content: str,
    taxonomy_term: Optional[str] = None,
    publish: bool = True
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Build the WordPress REST API payload for a given content type.

    Args:
        content_type:       e.g. "PROJECTS", "POLICY", "RESOURCES"
        generated_content:  raw text or JSON string from content.generated_content
        taxonomy_term:      optional term name to assign (e.g. "Adapt", "National")
        publish:            True = status "publish", False = status "draft"

    Returns:
        (success: bool, cpt_slug: str, payload: dict)
        On failure returns (False, "", {})
    """
    config = _load_config()

    type_config = config.get(content_type.upper())
    if not type_config:
        logger.error(f"content_mapper: no config found for content_type='{content_type}'")
        return False, "", {}

    cpt_slug = type_config.get("cpt_slug")
    if not cpt_slug:
        logger.error(f"content_mapper: cpt_slug is null for content_type='{content_type}' — WP team confirmation needed")
        return False, "", {}

    parsed = _parse_generated_content(generated_content)

    # --- Standard WP fields ---
    title = (
        parsed.get("title")
        or parsed.get("project_name")
        or parsed.get("resource_title")
        or parsed.get("policy_title")
        or parsed.get("newsletter_title")
        or parsed.get("headline")
        or "Untitled"
    )

    body = (
        parsed.get("body")
        or parsed.get("content")
        or parsed.get("main_content")
        or parsed.get("description")
        or parsed.get("project_description")
        or parsed.get("resource_body")
        or ""
    )

    payload: Dict[str, Any] = {
        "title": title,
        "content": body,
        "status": "publish" if publish else "draft",
    }

    # --- Taxonomy assignment ---
    taxonomy_key = type_config.get("taxonomy")
    taxonomy_terms = type_config.get("taxonomy_terms", {})

    if taxonomy_key and taxonomy_term and taxonomy_term in taxonomy_terms:
        term_id = taxonomy_terms[taxonomy_term]
        payload[taxonomy_key] = [term_id]
    elif taxonomy_key and taxonomy_terms:
        # Auto-assign the first available term if none specified
        first_term_id = next(iter(taxonomy_terms.values()))
        payload[taxonomy_key] = [first_term_id]

    # --- ACF fields ---
    acf_fields = type_config.get("acf_fields", {})
    acf_payload: Dict[str, Any] = {}

    for wp_field_name, our_content_key in acf_fields.items():
        if wp_field_name.startswith("_"):
            # Skip placeholder entries like "_pending"
            continue
        value = parsed.get(our_content_key)
        if value is not None:
            acf_payload[wp_field_name] = value

    if acf_payload:
        payload["acf"] = acf_payload

    logger.info(f"content_mapper: built payload for type='{content_type}' cpt='{cpt_slug}' title='{title}'")
    return True, cpt_slug, payload


def get_cpt_slug(content_type: str) -> Optional[str]:
    """Quick helper to get just the CPT slug for a content type."""
    config = _load_config()
    type_config = config.get(content_type.upper(), {})
    return type_config.get("cpt_slug")
