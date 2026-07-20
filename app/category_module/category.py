from fastapi import APIRouter, Request, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict

from auth_module.auth_utils import verify_token, require_session_auth

from category_module.category_utils import (
    get_categories_list, 
    create_category_record,
    get_parent_categories,
    check_root_exists
)
from category_module.category_responses import CategoryCreateRequest, CategoryCreateResponse, CategoryResponse
from service_utils.log_management import get_logger

# Set up logging
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/understanding", response_class=HTMLResponse)
@require_session_auth(redirect_url="/")
async def understanding_page(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """Render understanding categories HTML page."""
    
    try:
        results, msg = get_categories_list()
        parent_categories = get_parent_categories()
        has_root_category = check_root_exists()

        return templates.TemplateResponse(
            request=request,
            name="categories.htm",
            context={
                "data": results if results else [],
                "parent_categories": parent_categories,
                "has_root_category": has_root_category,
                "message": msg
            }
        )
    except Exception as e:
        logger.error(f"Error loading understanding page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="categories.htm",
            context={
                "data": [],
                "parent_categories": [],
                "has_root_category": False,
                "message": "Unable to load categories at this time"
            }
        )


@router.post("/create_category", response_model=CategoryCreateResponse)
def create_category(
    category_data: CategoryCreateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create a new category.
    
    Args:
        category_data: Category creation request data
        credentials: HTTP Bearer token for authentication
        
    Returns:
        CategoryCreateResponse with created category details
        
    Raises:
        HTTPException: If authentication fails or category creation fails
    """
    try:
        # Verify token
        token_data = verify_token(credentials.credentials)
        if not token_data:
            logger.warning("Invalid or expired token attempt")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        # Create category record
        category = create_category_record(
            category_name=category_data.category_name,
            is_parent=category_data.is_parent,
            parent_id=category_data.parent_id,
            is_root=category_data.is_root,
            is_active=category_data.is_active
        )
        
        if not category:
            logger.error(f"Failed to create category: {category_data.category_name}")
            raise HTTPException(
                status_code=500,
                detail="Unable to create category at this time"
            )
        
        # Convert to response model
        category_response = CategoryResponse(
            id=category.id,
            category_name=category.category_name,
            is_parent=category.is_parent,
            parent_id=category.parent_id,
            is_root=category.is_root,
            is_active=category.is_active,
            created_on=category.created_on,
            deleted_on=category.deleted_on,
            updated_on=category.updated_on
        )
        
        logger.info(f"Successfully created category: {category.category_name} (ID: {category.id})")
        
        return CategoryCreateResponse(
            message="Category created successfully",
            category=category_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_category: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while creating the category"
        )

