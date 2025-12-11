from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from content_module.content_responses import ContentCreateRequest, ContentCreateResponse, ContentResponse
from validations.content import ContentAddValidation
from models.content import ContentActionEnum, ContentApprovalStatusEnum

from auth_module.auth_utils import verify_token

from category_module.category_utils import get_categories_list

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/understanding", response_class=HTMLResponse)
async def understanding_page(request: Request):
    """Render understanding categories HTML page. Authentication handled by frontend JavaScript."""

    results, msg = get_categories_list()

    return templates.TemplateResponse(
        "categories.htm",
        {
            "request": request,
            "data": results if results else [],
            "message": msg
        }
    )

