from fastapi import APIRouter, Request, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict

from category_module.category_utils import get_categories_list
from page_modules.page_utils import get_page_by_id

from content_module.content_responses import (
    ContentCreateRequest, 
    ContentCreateResponse, 
    ContentResponse,
    AddDraftContentRequest,
    AddDraftContentResponse,
    PromptHistoryResponse,
    SaveAsDraftRequest
)

from content_module.prompt_history_utils import (
    create_prompt_history_record,
    add_draft_to_prompt_history,
)

from validations.content import ContentAddValidation
from auth_module.auth_utils import verify_token, require_session_auth
from models.content import ContentActionEnum

from content_module.content_utils import (
    get_unattached_content,
    create_content_record
)
from service_utils.log_management import get_logger

# Set up logging
logger = get_logger(__name__)


# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")



@router.post("/content", response_model=ContentCreateResponse)
async def create_content(
    content_data: ContentCreateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create new content entry.
    
    Args:
        content_data: Content creation request data
        credentials: Bearer token from Authorization header
    
    Returns:
        JSON response with created content information
    """
    try:
        token = credentials.credentials
        
        # Verify token
        success, status_code, message, payload = verify_token(token)
        
        if not success:
            logger.warning("Invalid token attempt in create_content")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Validate using ContentAddValidation
        try:
            validated_data = ContentAddValidation(
                category_id=content_data.category_id,
                prompt_data=content_data.prompt_data,
                action=content_data.action
            )
        except ValueError as e:
            logger.warning(f"Validation error in create_content: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid content data provided")
    
        # Create new content entry using utility function
        new_content = create_content_record(
            category_id=validated_data.category_id,
            prompt_data=validated_data.prompt_data,
            action=validated_data.action,
            user_id=payload.get("user_id"),
            content_type=content_data.content_type
        )
        
        # Initialize prompt_session_id as None
        prompt_session_id = None
        
        # If action is NEW, create prompt_history record
        if validated_data.action == ContentActionEnum.NEW:
            prompt_history, prompt_session_id, prompt_history_id = create_prompt_history_record(
                content_id=new_content["id"],
                prompt_data=validated_data.prompt_data
            )
        
        logger.info(f"Content created successfully: ID {new_content['id']}")

        return ContentCreateResponse(
            message="Content created successfully",
            content=ContentResponse(
                id=new_content["id"],
                category_id=new_content["category_id"],
                prompt_data=new_content.get("prompt_data"),
                generated_content=new_content.get("generated_content"),
                created_on=new_content["created_on"],
                deleted_on=new_content.get("deleted_on"),
                action=new_content["action"],
                approval_status=new_content["approval_status"],
                approval_status_date=new_content.get("approval_status_date"),
                accuracy=new_content.get("accuracy"),
                comments=new_content.get("comments"),
                quarter=new_content.get("quarter"),
                content_type=new_content.get("content_type")
            ),
            prompt_session_id=prompt_session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating content: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to create content at this time")




@router.get("/content", response_class=HTMLResponse)
@router.get("/content/{page_id:int}", response_class=HTMLResponse)
@require_session_auth(redirect_url="/")
async def content_generation_page(
    request: Request,
    page_id: Optional[int] = None,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """
    Render content generation page with empty textarea.
    """
    try:

        result = None
        is_page = False
        category_id = None

        if page_id:
            result = get_page_by_id(page_id=page_id)
            is_page = True
            category_id = result['category_id'] if result else None

        category_list, _ = get_categories_list()

        return templates.TemplateResponse(
            request=request,
            name="content.htm",
            context={
                "category_id": category_id,
                "latest_content": result,
                "category_list": category_list,
                "is_page": is_page
            }
        )
    except Exception as e:
        logger.error(f"Error loading content generation page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="content.htm",
            context={
                "category_id": None,
                "latest_content": None,
                "category_list": None,
                "is_page": False
            }
        )



@router.post("/content/draft", response_model=AddDraftContentResponse)
async def add_draft_content(
    draft_data: AddDraftContentRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Add draft content to an existing prompt history session.
    
    Args:
        draft_data: Draft content request data with prompt_text, content_id, and prompt_session_id
        credentials: Bearer token from Authorization header
    
    Returns:
        JSON response with created prompt_history information
    """
    try:
        token = credentials.credentials
        
        # Verify token
        success, status_code, message, payload = verify_token(token)
        
        if not success:
            logger.warning("Invalid token attempt in add_draft_content")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Add draft to existing prompt history session
        prompt_history = add_draft_to_prompt_history(
            prompt_session_id=draft_data.prompt_session_id,
            content_id=draft_data.content_id,
            prompt_text=draft_data.prompt_text
        )
        
        logger.info(f"Draft content added successfully: session {draft_data.prompt_session_id}")
        
        return AddDraftContentResponse(
            message="Draft content added successfully",
            prompt_history=PromptHistoryResponse(
                id=prompt_history["id"],
                prompt_session_id=prompt_history["prompt_session_id"],
                content_id=prompt_history["content_id"],
                user_prompt=prompt_history.get("user_prompt"),
                ai_response=prompt_history.get("ai_response"),
                prompt_type=prompt_history["prompt_type"],
                created_on=prompt_history["created_on"],
                deleted_on=prompt_history.get("deleted_on"),
                prompt_action=prompt_history.get("prompt_action")
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding draft content: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to add draft content at this time")


@router.get("/content/unattached", response_class=HTMLResponse)
@require_session_auth(redirect_url="/")
async def get_unattached(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """
    Fetch unattached content
    
    Returns:
        List of unattached content records
    """
    try:
        return templates.TemplateResponse(
            request=request,
            name="unattached_content.htm",
            context={
                "data": get_unattached_content(),
            }
        )
    except Exception as e:
        logger.error(f"Error loading content generation page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="unattached_content.htm",
            context={
                "data": None,
            }
        )

@router.post("/content/save_as_draft", response_model=AddDraftContentResponse)
async def user_save_as_draft(
    draft_data: SaveAsDraftRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Add draft content to an existing prompt history session.
    
    Args:
        draft_data: Draft content request data with prompt_text, content_id, and prompt_session_id
        credentials: Bearer token from Authorization header
    
    Returns:
        JSON response with created prompt_history information
    """
    try:
        token = credentials.credentials
        
        # Verify token
        success, status_code, message, payload = verify_token(token)
        
        if not success:
            logger.warning("Invalid token attempt in add_draft_content")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Add draft to existing prompt history session
        prompt_history = save_prompt_as_draft(
            prompt_id=draft_data.prompt_id
        )
        
        logger.info(f"Draft content added successfully: prompt ID {draft_data.prompt_id}")
        
        return AddDraftContentResponse(
            message="Draft content added successfully",
            prompt_history=PromptHistoryResponse(
                id=prompt_history["id"],
                prompt_session_id=prompt_history["prompt_session_id"],
                content_id=prompt_history["content_id"],
                user_prompt=prompt_history.get("user_prompt"),
                ai_response=prompt_history.get("ai_response"),
                prompt_type=prompt_history["prompt_type"],
                created_on=prompt_history["created_on"],
                deleted_on=prompt_history.get("deleted_on"),
                prompt_action=prompt_history["prompt_action"]
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding draft content: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to add draft content at this time")