from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from content_module.content_responses import ContentCreateRequest, ContentCreateResponse, ContentResponse
from validations.content import ContentAddValidation
from models.content import Content, ContentActionEnum, ContentApprovalStatusEnum
from service_utils.db_utils.pg_db import get_db
from auth_module.auth_utils import verify_token

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/content", response_class=HTMLResponse)
async def content_page(request: Request):
    """Render content editor HTML page. Authentication handled by frontend JavaScript."""
    return templates.TemplateResponse(
        "content.htm",
        {"request": request}
    )


@router.post("/content", response_model=ContentCreateResponse)
async def create_content(
    content_data: ContentCreateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Create new content entry.
    
    Args:
        content_data: Content creation request data
        credentials: Bearer token from Authorization header
        db: Database session
    
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
            task_run_id=content_data.task_run_id,
            category_id=content_data.category_id,
            prompt_data=content_data.prompt_data,
            generated_content=content_data.generated_content,
            action=ContentActionEnum(content_data.action) if content_data.action else ContentActionEnum.DRAFT,
            approval_status=ContentApprovalStatusEnum(content_data.approval_status) if content_data.approval_status else ContentApprovalStatusEnum.PENDING,
            accuracy=content_data.accuracy,
            comments=content_data.comments,
            quarter=content_data.quarter
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    
    # Create new content entry
    new_content = Content(
        task_run_id=validated_data.task_run_id,
        category_id=validated_data.category_id,
        prompt_data=validated_data.prompt_data,
        generated_content=validated_data.generated_content,
        action=validated_data.action,
        approval_status=validated_data.approval_status,
        approval_status_date=validated_data.approval_status_date,
        accuracy=validated_data.accuracy,
        comments=validated_data.comments,
        quarter=validated_data.quarter
    )
    
    try:
        db.add(new_content)
        db.commit()
        db.refresh(new_content)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    return ContentCreateResponse(
        message="Content created successfully",
        content=ContentResponse(
            id=new_content.id,
            task_run_id=new_content.task_run_id,
            category_id=new_content.category_id,
            prompt_data=new_content.prompt_data,
            generated_content=new_content.generated_content,
            created_on=new_content.created_on,
            deleted_on=new_content.deleted_on,
            action=new_content.action.value,
            approval_status=new_content.approval_status.value,
            approval_status_date=new_content.approval_status_date,
            accuracy=new_content.accuracy,
            comments=new_content.comments,
            quarter=new_content.quarter
        )
    )


