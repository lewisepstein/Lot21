from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    """Render projects HTML page. Authentication handled by frontend JavaScript."""
    return templates.TemplateResponse(
        request=request,
        name="projects.htm"
    )
