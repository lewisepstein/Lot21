"""Free Form AI module router."""

from fastapi import APIRouter, Request, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict

from auth_module.auth_utils import verify_token, require_session_auth
from freeform_module.freeform_utils import (
    create_project,
    get_user_projects,
    get_project_by_id,
    update_project,
    delete_project,
    save_chat_message,
    get_chat_history,
    chat_completion
)
from freeform_module.freeform_responses import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    ProjectListResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatHistoryResponse,
    ChatCompletionRequest
)
from service_utils.log_management import get_logger

# Set up logging
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/user/freeform", tags=["freeform"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")


# ============= PAGE ROUTES =============

@router.get("/", response_class=HTMLResponse)
@require_session_auth(redirect_url="/")
async def freeform_page(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """Render Free Form AI chat page."""
    try:
        return templates.TemplateResponse(
            request=request,
            name="freeform.htm"
        )
    except Exception as e:
        logger.error(f"Error loading Free Form page: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to load page at this time")


# ============= PROJECT API ROUTES =============

@router.post("/projects", response_model=ProjectResponse)
def create_new_project(
    project_data: ProjectCreateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new Free Form project."""
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail=message)

        # Extract user_id from token payload
        user_id = payload.get('user_id')

        # Create project
        project = create_project(
            project_name=project_data.project_name,
            project_description=project_data.project_description,
            created_by=user_id
        )

        logger.info(f"Created project: {project_data.project_name} for user {user_id}")
        return ProjectResponse(**project)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to create project at this time")


@router.get("/projects", response_model=ProjectListResponse)
def list_projects(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    include_inactive: bool = False
):
    """Get all projects for the authenticated user."""
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail=message)

        # Extract user_id from token payload
        user_id = payload.get('user_id')

        # Get projects
        projects, total = get_user_projects(user_id, include_inactive)

        return ProjectListResponse(
            projects=[ProjectResponse(**p) for p in projects],
            total=total
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving projects: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve projects at this time")


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get a specific project by ID."""
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail=message)

        # Get project
        project = get_project_by_id(project_id)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return ProjectResponse(**project)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving project {project_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve project at this time")


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_existing_project(
    project_id: int,
    project_data: ProjectUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update a project."""
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail=message)

        # Update project
        project = update_project(
            project_id=project_id,
            project_name=project_data.project_name,
            project_description=project_data.project_description,
            is_active=project_data.is_active
        )

        logger.info(f"Updated project {project_id}")
        return ProjectResponse(**project)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to update project at this time")


@router.delete("/projects/{project_id}")
def delete_existing_project(
    project_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a project."""
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail=message)

        # Delete project
        delete_project(project_id)

        logger.info(f"Deleted project {project_id}")
        return {"message": "Project deleted successfully"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to delete project at this time")


# ============= CHAT API ROUTES =============

@router.get("/projects/{project_id}/chat", response_model=ChatHistoryResponse)
def get_project_chat_history(
    project_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    limit: Optional[int] = None
):
    """Get chat history for a project."""
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail=message)

        # Get chat history
        messages, total = get_chat_history(project_id, limit)

        return ChatHistoryResponse(
            messages=[ChatMessageResponse(**m) for m in messages],
            total=total
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve chat history at this time")


@router.post("/chat")
def send_chat_message(
    chat_request: ChatCompletionRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Send a chat message and get AI response.
    This endpoint handles the complete chat flow: save user message, generate AI response, save AI response.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning(f"Token verification failed: {message}")
            raise HTTPException(status_code=status_code, detail=message)

        # Process chat completion
        user_msg, ai_msg = chat_completion(
            project_id=chat_request.project_id,
            user_message=chat_request.message,
            include_history=chat_request.include_history,
            attachments=chat_request.attachments
        )

        logger.info(f"Chat completion for project {chat_request.project_id}")

        return {
            "user_message": ChatMessageResponse(**user_msg),
            "ai_response": ChatMessageResponse(**ai_msg)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat completion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to process chat message at this time")
