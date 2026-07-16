"""
Content download routes.

Exports approved content as a formatted Word document or PDF —
a single item, or every approved item in a category as one file.
All endpoints require Bearer token authentication.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth_module.auth_utils import verify_token
from service_utils.log_management import get_logger

from download_module.download_utils import (
    get_approved_content_item,
    get_approved_category_content,
    get_freeform_message_item,
    get_prompt_response_item,
    safe_filename,
)
from download_module.document_builder import build_docx, build_pdf, build_png, build_jpg

logger = get_logger(__name__)

router = APIRouter(prefix="/user/download", tags=["download"])
security = HTTPBearer()

_FORMATS = {
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", build_docx),
    "pdf": ("application/pdf", build_pdf),
    "png": ("image/png", build_png),
    "jpg": ("image/jpeg", build_jpg),
}


def _require_auth(credentials: HTTPAuthorizationCredentials) -> dict:
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        logger.warning("Invalid token attempt in download routes")
        raise HTTPException(status_code=status_code, detail="Authentication failed")
    return payload


def _resolve_format(file_format: str):
    fmt = (file_format or "").lower().strip()
    if fmt not in _FORMATS:
        raise HTTPException(status_code=400, detail="file_format must be 'docx', 'pdf', 'png' or 'jpg'")
    return fmt, _FORMATS[fmt]


def _file_response(data: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/content/{content_id}")
async def download_content(
    content_id: int,
    file_format: str = Query(default="docx", description="'docx' or 'pdf'"),
    prompt_id: Optional[int] = Query(default=None, description="Download this specific response instead of the latest approved one"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Download a single approved content item (or a specific response) as Word or PDF."""
    _require_auth(credentials)
    fmt, (media_type, builder) = _resolve_format(file_format)

    if prompt_id is not None:
        item = get_prompt_response_item(content_id, prompt_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Response {prompt_id} not found for content {content_id}")
        if "body" not in item:
            raise HTTPException(status_code=400, detail="This response has no content to download")
    else:
        item = get_approved_content_item(content_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Content ID {content_id} not found")
        if "body" not in item:
            raise HTTPException(
                status_code=400,
                detail="Content must be approved before it can be downloaded",
            )

    try:
        data = builder(item["title"], [item])
    except Exception as e:
        logger.error(f"Error building {fmt} for content {content_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to generate document at this time")

    filename = safe_filename(item["title"], fmt)
    logger.info(f"Content {content_id} downloaded as {filename}")
    return _file_response(data, media_type, filename)


@router.get("/freeform/{message_id}")
async def download_freeform_message(
    message_id: int,
    file_format: str = Query(default="docx", description="'docx', 'pdf', 'png' or 'jpg'"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Download a Free Form AI chat message as Word, PDF, PNG or JPG."""
    _require_auth(credentials)
    fmt, (media_type, builder) = _resolve_format(file_format)

    item = get_freeform_message_item(message_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Message {message_id} not found")
    if "body" not in item:
        raise HTTPException(status_code=400, detail="This message has no text content to download")

    try:
        data = builder(item["title"], [item])
    except Exception as e:
        logger.error(f"Error building {fmt} for freeform message {message_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to generate document at this time")

    filename = safe_filename(item["title"], fmt)
    logger.info(f"Freeform message {message_id} downloaded as {filename}")
    return _file_response(data, media_type, filename)


@router.get("/category/{category_id}")
async def download_category(
    category_id: int,
    file_format: str = Query(default="docx", description="'docx' or 'pdf'"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Download all approved content in a category as a single Word or PDF file."""
    _require_auth(credentials)
    fmt, (media_type, builder) = _resolve_format(file_format)

    category_name, items = get_approved_category_content(category_id)
    if category_name is None:
        raise HTTPException(status_code=404, detail=f"Category ID {category_id} not found")
    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"No approved content found in category '{category_name}'",
        )

    doc_title = f"{category_name} — Approved Content"
    try:
        data = builder(doc_title, items)
    except Exception as e:
        logger.error(f"Error building {fmt} for category {category_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to generate document at this time")

    filename = safe_filename(category_name, fmt)
    logger.info(f"Category {category_id} ({len(items)} items) downloaded as {filename}")
    return _file_response(data, media_type, filename)
