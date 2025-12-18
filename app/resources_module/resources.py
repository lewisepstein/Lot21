from fastapi import APIRouter, Request, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict
import logging
from service_utils.log_management import get_logger
from auth_module.auth_utils import require_session_auth

# Set up logging
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/resources", response_class=HTMLResponse)
@require_session_auth(redirect_url="/")
async def resources_page(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """Render resources HTML page."""
    try:
        return templates.TemplateResponse(
            request=request,
            name="resources.htm"
        )
    except Exception as e:
        logger.error(f"Error loading resources page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="resources.htm"
        )
