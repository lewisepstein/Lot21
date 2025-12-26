from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
import logging

from content_module.content_responses import PromptHistoryResponse
from auth_module.auth_utils import verify_token
from service_utils.db_utils.pg_db import PostgresDB
from service_utils.log_management import get_logger

# Set up logging
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()


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
        
        db = PostgresDB()
        
        # Get all prompt history records for this session
        prompt_histories = db.read(
            "prompt_history",
            conditions={
                "prompt_session_id": prompt_session_id,
                "content_id": content_id,
                "deleted_on": None
            },
            order_by=[("created_on", True)]  # Ascending order (oldest first)
        )
        
        if not prompt_histories:
            return []
        
        # Convert to response models
        response_list = []
        for ph in prompt_histories:
            response_list.append(PromptHistoryResponse(
                id=ph["id"],
                prompt_session_id=ph["prompt_session_id"],
                content_id=ph["content_id"],
                user_prompt=ph.get("user_prompt"),
                ai_response=ph.get("ai_response"),
                prompt_type=ph["prompt_type"],
                created_on=ph["created_on"],
                deleted_on=ph.get("deleted_on"),
                prompt_action=ph.get("prompt_action")
            ))
        
        logger.info(f"Retrieved {len(response_list)} prompt history records")
        return response_list
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving prompt history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve prompt history at this time")