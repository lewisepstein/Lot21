from fastapi import Body
from fastapi import APIRouter, Request, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict

from auth_module.auth_utils import verify_token, require_session_auth

from page_modules.page_utils import (
    get_pages_list, 
    create_page_record,
    get_parent_pages,
    check_root_exists,
    get_page_statistics,
    get_page_by_id,
    update_page,
    delete_page
)
from page_modules.page_responses import PageCreateRequest, PageCreateResponse, PageResponse
from category_module.category_utils import get_parent_categories
from service_utils.log_management import get_logger

# Set up logging
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")

@router.get("/page-content/{page_id}", response_class=HTMLResponse)
@require_session_auth(redirect_url="/")
async def page_content(
    request: Request,
    page_id: int,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    try:
        results = get_page_by_id(page_id=page_id)
        if not results:
            raise HTTPException(status_code=404, detail="Page not found")
        return templates.TemplateResponse(
            request=request,
            name="page_content.htm",
            context={
                "data": results,
                "message": ""
            }
        )
    except Exception as e:
        logger.error(f"Error loading pages page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="page_content.htm",
            context={
                "data": [],
                "message": "Unable to load pages at this time"
            }
        )


@router.get("/pages/{category_id}", response_class=HTMLResponse)
@require_session_auth(redirect_url="/")
async def pages_page(
    request: Request,
    category_id: int,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """Render pages HTML page filtered by category_id."""
    
    try:
        results, msg = get_pages_list(category_id=category_id)
        # parent_pages = get_parent_pages()
        # has_root_page = check_root_exists()

        return templates.TemplateResponse(
            request=request,
            name="page.htm",
            context={
                "data": results if results else [],
                # "parent_pages": parent_pages,
                # "has_root_page": has_root_page,
                "message": msg,
                "category_id": category_id
            }
        )
    except Exception as e:
        logger.error(f"Error loading pages page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="page.htm",
            context={
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
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail=message)
        
        # Extract user_id from token payload
        user_id = payload.get('user_id')
        
        # Log incoming request data for debugging
        logger.info(f"Creating page with data: name={page_data.page_name}, category_id={page_data.category_id}, "
                   f"scrape_data={page_data.scrape_data}, description={page_data.description}")
        
        try:
            # Create page record
            page_data_dict = create_page_record(
                page_name=page_data.page_name,
                category_id=page_data.category_id,
                created_by=user_id,
                is_active=page_data.is_active,
                content=page_data.content,
                source_url=page_data.source_url,
                scrape_data=page_data.scrape_data,
                description=page_data.description
            )
        except ValueError as ve:
            logger.warning(f"Page creation validation failed: {ve}")
            raise HTTPException(status_code=400, detail=str(ve))
        
        # Convert to response model
        page_response = PageResponse(**page_data_dict)
        
        logger.info(f"Successfully created page: {page_data.page_name} (ID: {page_data_dict['id']})")
        
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
@require_session_auth(redirect_url="/")
async def page_settings(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """Render page settings page with statistics."""
    
    try:
        stats = get_page_statistics()
        categories = get_parent_categories(is_parent=False, is_root=False, is_active=True)
        
        return templates.TemplateResponse(
            request=request,
            name="page_settings.htm",
            context={
                "assigned_pages": stats['assigned_pages'],
                "unassigned_pages": stats['unassigned_pages'],
                "active_pages": stats['active_pages'],
                "inactive_pages": stats['inactive_pages'],
                "pages_with_content": stats['pages_with_content'],
                "pages_without_content": stats['pages_without_content'],
                "pages": stats['pages'],
                "categories": categories if categories else []
            }
        )
    except Exception as e:
        logger.error(f"Error loading page settings: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="page_settings.htm",
            context={
                "assigned_pages": 0,
                "unassigned_pages": 0,
                "active_pages": 0,
                "inactive_pages": 0,
                "pages_with_content": 0,
                "pages_without_content": 0,
                "pages": [],
                "categories": []
            }
        )


@router.get("/get_page/{page_id}")
async def get_page(
    page_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get a single page by ID.
    
    Args:
        page_id: The ID of the page to retrieve
        credentials: HTTP Bearer token for authentication
        
    Returns:
        Page details
        
    Raises:
        HTTPException: If authentication fails or page not found
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Get page
        page = get_page_by_id(page_id)
        
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        
        logger.info(f"Retrieved page {page_id}")
        return page
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_page: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while retrieving the page"
        )


@router.put("/update_page/{page_id}")
async def update_page_endpoint(
    page_id: int,
    page_data: PageCreateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Update an existing page.
    
    Args:
        page_id: The ID of the page to update
        page_data: Page update request data
        credentials: HTTP Bearer token for authentication
        
    Returns:
        Updated page details
        
    Raises:
        HTTPException: If authentication fails or update fails
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Extract user_id from token payload
        user_id = payload.get('user_id')
        
        logger.info(f"Updating page {page_id} with data: name={page_data.page_name}, "
                   f"category_id={page_data.category_id}, is_active={page_data.is_active}")
        
        try:
            # Update page record
            updated_page = update_page(
                page_id=page_id,
                page_name=page_data.page_name,
                category_id=page_data.category_id,
                is_active=page_data.is_active,
                content=page_data.content,
                source_url=page_data.source_url,
                description=page_data.description,
                updated_by=user_id
            )
        except ValueError as ve:
            logger.warning(f"Page update validation failed: {ve}")
            raise HTTPException(status_code=400, detail=str(ve))
        
        logger.info(f"Successfully updated page: {updated_page['page_name']} (ID: {page_id})")
        
        return {
            "message": "Page updated successfully",
            "page": updated_page
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_page: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while updating the page"
        )

@router.delete("/delete_page/{page_id}")
async def delete_page_record(
    page_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Hard delete a page and all related records.
    """
    try:
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        try:
            delete_page(page_id)
        except ValueError as ve:
            logger.warning(f"Page deletion validation failed: {ve}")
            raise HTTPException(status_code=400, detail=str(ve))
        logger.info(f"Successfully hard deleted page ID: {page_id}")
        return {"message": "Page hard deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_page: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while deleting the page"
        )

@router.delete("/delete_pages")
async def delete_pages(
    body: dict = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Delete multiple pages and all related records.
    """
    try:
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        page_ids = body.get("page_ids")
        if not page_ids or not isinstance(page_ids, list):
            raise HTTPException(status_code=400, detail="page_ids must be a list of IDs")
        failed = []
        for pid in page_ids:
            try:
                delete_page(pid)
            except Exception as e:
                logger.warning(f"Failed to delete page {pid}: {e}")
                failed.append(pid)
        if failed:
            return {"message": f"Some pages could not be deleted: {failed}", "failed_ids": failed}
        return {"message": "Pages deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_pages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while hard deleting pages"
        )