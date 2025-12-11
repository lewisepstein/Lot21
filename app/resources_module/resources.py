from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/resources", response_class=HTMLResponse)
async def resources_page(request: Request):
    """Render resources HTML page. Authentication handled by frontend JavaScript."""
    return templates.TemplateResponse(
        "resources.htm",
        {"request": request}
    )
