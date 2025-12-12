from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from content_module.content_responses import (
    ContentCreateRequest, 
    ContentCreateResponse, 
    ContentResponse,
    AddDraftContentRequest,
    AddDraftContentResponse,
    PromptHistoryResponse
)

from content_module.content_utils import (
    get_latest_content, 
    create_content_record
)

from content_module.prompt_history_utils import (
    create_prompt_history_record,
    add_draft_to_prompt_history
)

from validations.content import ContentAddValidation
from auth_module.auth_utils import verify_token
from models.content import ContentActionEnum

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/content/{category_id}", response_class=HTMLResponse)
async def content_page(request: Request, category_id: int):
    """
    Render content editor HTML page with category context.
    Fetches the latest content for the category if available.
    Authentication handled by frontend JavaScript.
    
    Args:
        category_id: ID of the category to generate content for
    """
    # Get the latest content for this category
    latest_content = get_latest_content(category_id)

    print(latest_content)
    
    return templates.TemplateResponse(
        "content.htm",
        {
            "request": request, 
            "category_id": category_id,
            "latest_content": latest_content
        }
    )


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
    token = credentials.credentials
    
    # Verify token
    success, status_code, message, payload = verify_token(token)
    
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # Validate using ContentAddValidation
    try:
        validated_data = ContentAddValidation(
            category_id=content_data.category_id,
            prompt_data=content_data.prompt_data,
            action=content_data.action
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    
    try:
        # Create new content entry using utility function
        new_content = create_content_record(
            category_id=validated_data.category_id,
            prompt_data=validated_data.prompt_data,
            action=validated_data.action,
            user_id=payload.get("user_id")
        )
        
        # Initialize prompt_session_id as None
        prompt_session_id = None
        
        # If action is NEW, create prompt_history record
        if validated_data.action == ContentActionEnum.NEW:
            prompt_history, prompt_session_id, prompt_history_id = create_prompt_history_record(
                content_id=new_content["id"],
                prompt_data=validated_data.prompt_data
            )
        
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
                quarter=new_content.get("quarter")
            ),
            prompt_session_id=prompt_session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


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
    token = credentials.credentials
    
    # Verify token
    success, status_code, message, payload = verify_token(token)
    
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    try:
        # Add draft to existing prompt history session
        prompt_history = add_draft_to_prompt_history(
            prompt_session_id=draft_data.prompt_session_id,
            content_id=draft_data.content_id,
            prompt_text=draft_data.prompt_text
        )
        
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
                deleted_on=prompt_history.get("deleted_on")
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


