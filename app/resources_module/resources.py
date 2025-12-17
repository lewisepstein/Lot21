from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/resources", response_class=HTMLResponse)
async def resources_page(request: Request):
    """Render resources HTML page. Authentication handled by frontend JavaScript."""
    try:
        return templates.TemplateResponse(
            "resources.htm",
            {"request": request}
        )
    except Exception as e:
        logger.error(f"Error loading resources page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "resources.htm",
            {"request": request}
        )
