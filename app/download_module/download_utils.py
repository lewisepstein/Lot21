"""
Utility functions for the content download module.

Fetches approved content for export. A content item counts as "approved"
when either:
  - the content record itself has approval_status = APPROVED, or
  - it has at least one prompt_history row with prompt_action = APPROVED
    (the approval flow on the content page updates prompt_history only).
"""
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from service_utils.db_utils.pg_db import PostgresDB
from service_utils.log_management import get_logger

logger = get_logger(__name__)


def _enum_value(value: Any) -> Any:
    """Return .value for enum-like objects, the raw value otherwise."""
    return value.value if hasattr(value, "value") else value


def _normalize_body(raw: Any) -> Optional[str]:
    """
    Content bodies are stored either as plain markdown or as JSON like
    {"text": "...", "images": ["url", ...]}. Return printable markdown,
    or None when there is nothing to export.
    """
    if not raw:
        return None
    text = str(raw).strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            data = None
        if isinstance(data, dict):
            parts = []
            inner = (data.get("text") or "").strip()
            if inner:
                parts.append(inner)
            images = data.get("images") or []
            if images:
                parts.append("\n".join(f"- Image: {url}" for url in images if url))
            text = "\n\n".join(parts)
    return text or None


def _latest_approved_response(db: PostgresDB, content_id: int) -> Optional[Dict[str, Any]]:
    """Return the most recent APPROVED prompt_history row for a content record."""
    try:
        rows = db.read(
            "prompt_history",
            conditions={
                "content_id": content_id,
                "prompt_action": "APPROVED",
                "deleted_on": None,
            },
            order_by=[("updated_on", False)],
            limit=1,
        )
        return rows[0] if rows else None
    except Exception as e:
        logger.error(f"Error reading approved prompts for content {content_id}: {e}")
        return None


def _build_export_item(db: PostgresDB, content: Dict[str, Any],
                       page_names: Optional[Dict[int, str]] = None) -> Optional[Dict[str, Any]]:
    """
    Resolve the export payload for a content record.
    Returns None when the record has no approved body to export.
    """
    approved_prompt = _latest_approved_response(db, content["id"])

    body = None
    approved_on = None
    title = None

    if approved_prompt and _normalize_body(approved_prompt.get("ai_response")):
        body = _normalize_body(approved_prompt.get("ai_response"))
        approved_on = approved_prompt.get("updated_on")
        title = approved_prompt.get("prompt_name")
    elif _enum_value(content.get("approval_status")) == "APPROVED":
        body = _normalize_body(content.get("generated_content"))
        approved_on = content.get("approval_status_date")

    if not body:
        return None

    if not title:
        page_id = content.get("page_id")
        if page_names and page_id and page_names.get(page_id):
            title = page_names[page_id]
        else:
            content_type = _enum_value(content.get("content_type")) or "Content"
            title = f"{str(content_type).title()} #{content['id']}"

    return {
        "content_id": content["id"],
        "title": title,
        "content_type": _enum_value(content.get("content_type")),
        "quarter": content.get("quarter"),
        "approved_on": approved_on,
        "created_on": content.get("created_on"),
        "body": body,
    }


def get_approved_content_item(content_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a single approved content item ready for export.

    Returns:
        Export item dict, None if the content does not exist, or a dict with
        only {"content_id": ...} when it exists but is not approved.
    """
    db = PostgresDB()
    rows = db.read("content", conditions={"id": content_id, "deleted_on": None}, limit=1)
    if not rows:
        return None

    item = _build_export_item(db, rows[0])
    if item is None:
        return {"content_id": content_id}
    return item


def get_prompt_response_item(content_id: int, prompt_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a specific prompt_history response for export, regardless of
    approval state — used to download freshly generated responses.

    Returns:
        Export item dict, None if the content or prompt does not exist, or a
        dict with only {"content_id": ...} when the response has no body.
    """
    db = PostgresDB()
    contents = db.read("content", conditions={"id": content_id, "deleted_on": None}, limit=1)
    if not contents:
        return None
    content = contents[0]

    prompts = db.read(
        "prompt_history",
        conditions={"id": prompt_id, "content_id": content_id, "deleted_on": None},
        limit=1,
    )
    if not prompts:
        return None
    prompt = prompts[0]

    body = _normalize_body(prompt.get("ai_response"))
    if not body:
        return {"content_id": content_id}

    title = prompt.get("prompt_name")
    if not title:
        content_type = _enum_value(content.get("content_type")) or "Content"
        title = f"{str(content_type).title()} #{content['id']}"

    approved_on = None
    if _enum_value(prompt.get("prompt_action")) == "APPROVED":
        approved_on = prompt.get("updated_on")

    return {
        "content_id": content["id"],
        "title": title,
        "content_type": _enum_value(content.get("content_type")),
        "quarter": content.get("quarter"),
        "approved_on": approved_on,
        "created_on": content.get("created_on"),
        "body": body,
    }


def get_freeform_message_item(message_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a Free Form AI chat message for export.

    Returns:
        Export item dict, None if the message does not exist, or a dict with
        only {"message_id": ...} when it has no text body to export.
    """
    db = PostgresDB()
    rows = db.read("freeform_chat", conditions={"id": message_id, "deleted_on": None}, limit=1)
    if not rows:
        return None
    message = rows[0]

    content = str(message.get("content") or "")
    body = None if content.strip().startswith("data:image/") else _normalize_body(content)
    if not body:
        return {"message_id": message_id}

    title = "Free Form AI"
    projects = db.read(
        "freeform_projects",
        conditions={"id": message["project_id"], "deleted_on": None},
        columns=["project_name"],
        limit=1,
    )
    if projects and projects[0].get("project_name"):
        title = projects[0]["project_name"]

    return {
        "content_id": message["id"],
        "title": title,
        "content_type": None,
        "quarter": None,
        "approved_on": None,
        "created_on": message.get("created_on"),
        "body": body,
    }


def get_approved_category_content(category_id: int) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Fetch all approved content in a category, ready for export.

    Content belongs to a category either directly (content.category_id) or
    through its page (pages.category_id).

    Returns:
        (category_name or None if category missing, list of export items)
    """
    db = PostgresDB()

    categories = db.read(
        "categories",
        conditions={"id": category_id, "deleted_on": None},
        columns=["id", "category_name"],
        limit=1,
    )
    if not categories:
        return None, []
    category_name = categories[0].get("category_name") or f"Category {category_id}"

    pages = db.read(
        "pages",
        conditions={"category_id": category_id, "deleted_on": None},
        columns=["id", "page_name"],
    ) or []
    page_names = {p["id"]: p.get("page_name") for p in pages}
    page_ids = list(page_names.keys())

    contents = db.read("content", conditions={"category_id": category_id, "deleted_on": None}) or []
    seen_ids = {c["id"] for c in contents}

    if page_ids:
        page_contents = db.read(
            "content",
            conditions={"page_id__in": page_ids, "deleted_on": None},
        ) or []
        for c in page_contents:
            if c["id"] not in seen_ids:
                contents.append(c)
                seen_ids.add(c["id"])

    contents.sort(key=lambda c: (c.get("created_on") or datetime.min.replace(tzinfo=timezone.utc)))

    items = []
    for content in contents:
        item = _build_export_item(db, content, page_names=page_names)
        if item:
            items.append(item)

    return category_name, items


def safe_filename(name: str, extension: str) -> str:
    """Build a safe download filename like 'lottie_understanding_20260708.docx'."""
    stem = re.sub(r"[^A-Za-z0-9]+", "_", (name or "content")).strip("_").lower() or "content"
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"lottie_{stem}_{date_part}.{extension}"
