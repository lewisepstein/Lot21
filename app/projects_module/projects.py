from fastapi import APIRouter, Request, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict
from auth_module.auth_utils import require_session_auth

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/projects", response_class=HTMLResponse)
@require_session_auth(redirect_url="/")
async def projects_page(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """Render projects HTML page."""
    return templates.TemplateResponse(
        request=request,
        name="projects.htm"
    )
