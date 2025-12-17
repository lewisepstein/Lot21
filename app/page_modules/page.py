from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from auth_module.auth_utils import verify_token

from page_modules.page_utils import (
    get_pages_list, 
    create_page_record,
    get_parent_pages,
    check_root_exists,
    get_page_statistics
)
from page_modules.page_responses import PageCreateRequest, PageCreateResponse, PageResponse

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/pages/{category_id}", response_class=HTMLResponse)
async def pages_page(request: Request, category_id: int):
    """Render pages HTML page filtered by category_id. Authentication handled by frontend JavaScript."""
    
    try:
        results, msg = get_pages_list(category_id=category_id)
        parent_pages = get_parent_pages()
        has_root_page = check_root_exists()

        return templates.TemplateResponse(
            "page.htm",
            {
                "request": request,
                "data": results if results else [],
                "parent_pages": parent_pages,
                "has_root_page": has_root_page,
                "message": msg,
                "category_id": category_id
            }
        )
    except Exception as e:
        logger.error(f"Error loading pages page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "page.htm",
            {
                "request": request,
                "data": [],
                "parent_pages": [],
                "has_root_page": False,
                "message": "Unable to load pages at this time"
            }
        )


@router.post("/create_page", response_model=PageCreateResponse)
async def create_page(
    page_data: PageCreateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create a new page.
    
    Args:
        page_data: Page creation request data
        credentials: HTTP Bearer token for authentication
        
    Returns:
        PageCreateResponse with created page details
        
    Raises:
        HTTPException: If authentication fails or page creation fails
    """
    try:
        # Verify token
        token_data = verify_token(credentials.credentials)
        if not token_data:
            logger.warning("Invalid or expired token attempt")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        # Create page record
        page = create_page_record(
            page_name=page_data.page_name,
            category_id=page_data.category_id,
            created_by=page_data.created_by,
            is_parent=page_data.is_parent,
            parent_id=page_data.parent_id,
            is_root=page_data.is_root,
            is_active=page_data.is_active
        )
        
        if not page:
            logger.error(f"Failed to create page: {page_data.page_name}")
            raise HTTPException(
                status_code=500,
                detail="Unable to create page at this time"
            )
        
        # Convert to response model
        page_response = PageResponse(
            id=page.id,
            page_name=page.page_name,
            category_id=page.category_id,
            created_by=page.created_by,
            is_parent=page.is_parent,
            parent_id=page.parent_id,
            is_root=page.is_root,
            is_active=page.is_active,
            created_on=page.created_on,
            deleted_on=page.deleted_on,
            updated_on=page.updated_on
        )
        
        logger.info(f"Successfully created page: {page.page_name} (ID: {page.id})")
        
        return PageCreateResponse(
            message="Page created successfully",
            page=page_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_page: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while creating the page"
        )


@router.get("/page-settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    """Render page settings page with statistics. Authentication handled by frontend JavaScript."""
    
    try:
        stats = get_page_statistics()
        
        return templates.TemplateResponse(
            "page_settings.htm",
            {
                "request": request,
                "assigned_pages": stats['assigned_pages'],
                "unassigned_pages": stats['unassigned_pages'],
                "active_pages": stats['active_pages'],
                "inactive_pages": stats['inactive_pages'],
                "pages_with_content": stats['pages_with_content'],
                "pages_without_content": stats['pages_without_content'],
                "pages": stats['pages']
            }
        )
    except Exception as e:
        logger.error(f"Error loading page settings: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "page_settings.htm",
            {
                "request": request,
                "assigned_pages": 0,
                "unassigned_pages": 0,
                "active_pages": 0,
                "inactive_pages": 0,
                "pages_with_content": 0,
                "pages_without_content": 0,
                "pages": []
            }
        )
