from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from content_module.content_responses import ContentCreateRequest, ContentCreateResponse, ContentResponse
from validations.content import ContentAddValidation
from service_utils.db_utils.pg_db import PostgresDB
from auth_module.auth_utils import verify_token
from models.content import ContentActionEnum, ContentApprovalStatusEnum

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
    Authentication handled by frontend JavaScript.
    
    Args:
        category_id: ID of the category to generate content for
    """
    return templates.TemplateResponse(
        "content.htm",
        {"request": request, "category_id": category_id}
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
            prompt_data=content_data.prompt_data
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    
    # Get database instance
    db = PostgresDB()
    
    # Prepare content data for insertion
    content_dict = {
        "category_id": validated_data.category_id,
        "prompt_data": validated_data.prompt_data,
        "action": ContentActionEnum.DRAFT.value,
        "approval_status": ContentApprovalStatusEnum.PENDING.value,
        "created_by": payload.get("user_id")
    }
    
    try:
        # Create new content entry
        new_content = db.create("content", content_dict)
        
        if not new_content:
            raise HTTPException(status_code=500, detail="Failed to create content")
        
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
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


