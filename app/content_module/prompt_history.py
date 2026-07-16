from fastapi import APIRouter, HTTPException, Request, Depends, Cookie
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, List, Optional
from fastapi.templating import Jinja2Templates

from content_module.content_responses import PromptHistoryResponse
from auth_module.auth_utils import verify_token
from service_utils.log_management import get_logger
from content_module.prompt_history_utils import (
    get_prompt_histories,
    update_prompt_action,
    get_all_prompts,
    get_content_version_history,
    restore_content_version
)

from content_module.content_responses import (
    SaveAsDraftRequest,
    AddDraftContentResponse
)

# Set up logging
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/prompt_history/{prompt_session_id}/{content_id}", response_model=List[PromptHistoryResponse])
async def get_prompt_history(
    prompt_session_id: str,
    content_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get all prompt history records for a given session and content.
    
    Args:
        prompt_session_id: UUID of the prompt session
        content_id: ID of the content record
        credentials: Bearer token from Authorization header
    
    Returns:
        List of prompt history records ordered by created_on
    """
    try:
        token = credentials.credentials
        
        # Verify token
        success, status_code, message, payload = verify_token(token)
        
        if not success:
            logger.warning("Invalid token attempt in get_prompt_history")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        response_list = get_prompt_histories(
            prompt_session_id=prompt_session_id,
            content_id=content_id
        )
        
        logger.info(f"Retrieved {len(response_list)} prompt history records")
        return response_list
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving prompt history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve prompt history at this time")
    

@router.get("/content/{content_id}/history")
async def get_content_history(
    content_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Draft History: every saved version of a content, newest first."""
    try:
        success, status_code, _, _ = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in get_content_history")
            raise HTTPException(status_code=status_code, detail="Authentication failed")

        versions = get_content_version_history(content_id)
        logger.info(f"Draft history: {len(versions)} versions for content {content_id}")
        return {"content_id": content_id, "versions": versions}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving content history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve draft history at this time")


@router.post("/content/{content_id}/restore/{version_id}")
async def restore_content_history_version(
    content_id: int,
    version_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Draft History: restore an old version as the new latest (non-destructive)."""
    try:
        success, status_code, _, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in restore_content_history_version")
            raise HTTPException(status_code=status_code, detail="Authentication failed")

        new_version = restore_content_version(
            content_id=content_id,
            version_id=version_id,
            user_id=payload.get("user_id")
        )
        return {
            "message": "Version restored",
            "restored_from": version_id,
            "new_version_id": new_version["id"],
            "prompt_session_id": new_version["prompt_session_id"]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring content version: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to restore this version at this time")


@router.post("/prompt_history/set_action", response_model=AddDraftContentResponse)
async def set_action_prompt_history(
    request: SaveAsDraftRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get all prompt history records for a given session and content.
    
    Args:
        prompt_session_id: UUID of the prompt session
        content_id: ID of the content record
        credentials: Bearer token from Authorization header
    
    Returns:
        List of prompt history records ordered by created_on
    """
    try:
        token = credentials.credentials
        
        # Verify token
        success, status_code, message, payload = verify_token(token)
        
        if not success:
            logger.warning("Invalid token attempt in get_prompt_history")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        prompt_history = update_prompt_action(
            id=request.prompt_history_id,
            prompt_action=request.prompt_action,
            prompt_name=request.prompt_name,
            prompt_description=request.prompt_description        
        )

        if prompt_history:
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
        else:
            logger.info(f"Failed to save prompt history {request.prompt_history_id} as draft")
            raise HTTPException(status_code=500, detail="Failed to save prompt history as draft")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving prompt history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve prompt history at this time")
    

@router.get("/prompt_history_data",response_class=HTMLResponse)
@router.get("/prompt_history_data/{prompt_session_id:str}", response_class=HTMLResponse)
async def get_all_prompt_history(
    request: Request,
    prompt_session_id: Optional[str] = None,
    content_id: Optional[int] = None,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """
    Get all prompt history records for a given session and content.
    
    Args:
        prompt_session_id: UUID of the prompt session
        content_id: ID of the content record
        credentials: Bearer token from Authorization header
    """

    data = get_all_prompts(
        prompt_session_id=prompt_session_id,
        content_id=content_id
    )

    return templates.TemplateResponse(
        request=request,
        name="prompt_history.htm",
        context={
            "data": data,
        }
    )
    
