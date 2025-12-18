from fastapi import APIRouter, Request, Depends, HTTPException, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
import logging

from auth_module.auth_utils import verify_token, require_session_auth
from agent_module.agent_utils import (
    load_training_data_to_weaviate,
    get_training_history,
    delete_training_record as delete_training_record_util,
    update_training_record,
    get_version_history,
    restore_from_version
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


@router.get("/settings", response_class=HTMLResponse)
@require_session_auth(redirect_url="/")
async def settings_page(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    authenticated_user: Optional[Dict] = None
):
    """
    Render agent settings page.
    """
    try:
        return templates.TemplateResponse(
            request=request,
            name="agent.htm"
        )
    except Exception as e:
        logger.error(f"Error loading settings page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="agent.htm"
        )


@router.post("/settings/api")
async def save_api_credentials(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Save API credentials for web search and image generation.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in save_api_credentials")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Get request data
        data = await request.json()
        
        # TODO: Implement logic to save API credentials to database
        # For now, return success response
        
        logger.info("API credentials saved successfully")
        return {
            "success": True,
            "message": "API credentials saved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving API credentials: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to save API credentials at this time")


@router.get("/settings/api")
async def get_api_credentials(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get API credentials status (without revealing actual keys).
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in get_api_credentials")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # TODO: Implement logic to check if API credentials exist in database
        
        return {
            "web_search_configured": False,
            "image_gen_configured": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving API credentials: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve API credentials at this time")


@router.post("/settings/schedule")
async def save_schedule_settings(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Save scheduling preferences for content generation.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in save_schedule_settings")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Get request data
        data = await request.json()
        
        # TODO: Implement logic to save schedule settings to database
        
        logger.info("Schedule settings saved successfully")
        return {
            "success": True,
            "message": "Schedule settings saved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving schedule settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to save schedule settings at this time")


@router.get("/settings/schedule")
async def get_schedule_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current scheduling preferences.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in get_schedule_settings")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # TODO: Implement logic to retrieve schedule settings from database
        
        return {
            "understanding_schedule": "weekly",
            "newsletter_schedule": "weekly",
            "social_schedule": "daily",
            "preferred_time": "09:00",
            "auto_publish": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving schedule settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve schedule settings at this time")


@router.post("/settings/content")
async def save_content_settings(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Save content style preferences.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in save_content_settings")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Get request data
        data = await request.json()
        
        # TODO: Implement logic to save content settings to database
        
        logger.info("Content preferences saved successfully")
        return {
            "success": True,
            "message": "Content preferences saved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving content settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to save content preferences at this time")


@router.get("/settings/content")
async def get_content_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current content style preferences.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in get_content_settings")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # TODO: Implement logic to retrieve content settings from database
        
        return {
            "writing_tone": "professional",
            "target_audience": "general",
            "content_length": "medium",
            "include_images": True,
            "include_sources": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving content settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve content preferences at this time")


@router.post("/settings/model")
async def save_model_settings(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Save AI language model preferences.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in save_model_settings")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Get request data
        data = await request.json()
        
        # TODO: Implement logic to save model settings to database
        
        logger.info("Language model saved successfully")
        return {
            "success": True,
            "message": "Language model saved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving model settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to save model settings at this time")


@router.get("/settings/model")
async def get_model_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current AI language model preferences.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in get_model_settings")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # TODO: Implement logic to retrieve model settings from database
        
        return {
            "language_model": "gpt-4"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving model settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve model settings at this time")


@router.post("/settings/image-model")
async def save_image_model_settings(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Save AI image generation model preferences.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in save_image_model_settings")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Get request data
        data = await request.json()
        
        # TODO: Implement logic to save image model settings to database
        
        logger.info("Image generation model saved successfully")
        return {
            "success": True,
            "message": "Image generation model saved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving image model settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to save image model settings at this time")


@router.get("/settings/image-model")
async def get_image_model_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current AI image generation model preferences.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in get_image_model_settings")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # TODO: Implement logic to retrieve image model settings from database
        
        return {
            "image_model": "dall-e-3"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving image model settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve image model settings at this time")


@router.get("/settings/training-history")
async def get_training_history_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get training data loading history from weaviate_data table.
    """
    try:
        # Verify token
        success, status_code, message, payload = verify_token(credentials.credentials)
        if not success:
            logger.warning("Invalid token attempt in get_training_history")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        user_id = payload.get("user_id")
        if not user_id:
            logger.warning("Missing user_id in token payload")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        history = get_training_history(user_id=user_id, limit=50)
        return {"history": history}
        
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"Runtime error fetching training history: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to fetch training history at this time")
    except Exception as e:
        logger.error(f"Unexpected error fetching training history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to fetch training history at this time")


@router.post("/settings/train-model")
async def load_training_data(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Load training data into Weaviate vector database and store metadata in database.
    Chunks the data and stores it with embeddings.
    """
    try:
        # Verify token and get user info
        success, status_code, message, payload = verify_token(credentials.credentials)
        
        if not success or not payload:
            logger.warning("Invalid token attempt in load_training_data")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        user_id = payload.get("user_id")
        
        if not user_id:
            logger.warning("Missing user_id in token payload")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        # Get request data
        data = await request.json()
        training_data = data.get("training_data", "")
        collection_name = data.get("collection_name", "training_data")
        description = data.get("description", "")
        
        if not training_data.strip():
            raise HTTPException(status_code=400, detail="Training data cannot be empty")
        
        if not collection_name.strip():
            raise HTTPException(status_code=400, detail="Collection name cannot be empty")
        
        # Use the utility function to load data into Weaviate and save to database
        result = load_training_data_to_weaviate(
            training_data=training_data,
            collection_name=collection_name,
            user_id=user_id,
            description=description
        )
        
        logger.info(f"Training data loaded successfully for user {user_id}")
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error in load_training_data: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid training data provided")
    except RuntimeError as e:
        logger.error(f"Runtime error loading data to Weaviate: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to load training data at this time")
    except Exception as e:
        logger.error(f"Unexpected error loading data to Weaviate: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to load training data at this time")


@router.delete("/settings/training-record/{record_id}")
async def delete_training_record(
    record_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Delete (soft delete) a training record from the database.
    """
    try:
        # Verify token and get user info
        success, status_code, message, payload = verify_token(credentials.credentials)
        
        if not success or not payload:
            logger.warning("Invalid token attempt in delete_training_record")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        user_id = payload.get("user_id")
        
        if not user_id:
            logger.warning("Missing user_id in token payload")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        result = delete_training_record_util(record_id=record_id, user_id=user_id)
        logger.info(f"Training record {record_id} deleted successfully")
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Record not found: {str(e)}")
        raise HTTPException(status_code=404, detail="Training record not found")
    except RuntimeError as e:
        logger.error(f"Runtime error deleting training record: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to delete training record at this time")
    except Exception as e:
        logger.error(f"Unexpected error deleting training record: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to delete training record at this time")


@router.put("/settings/training-record/{record_id}")
async def update_training_record_endpoint(
    record_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Update an existing training record with new data.
    """
    try:
        # Verify token and get user info
        success, status_code, message, payload = verify_token(credentials.credentials)
        
        if not success or not payload:
            logger.warning("Invalid token attempt in update_training_record")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        user_id = payload.get("user_id")
        
        if not user_id:
            logger.warning("Missing user_id in token payload")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        # Get request data
        data = await request.json()
        training_data = data.get("training_data", "")
        description = data.get("description", "")
        
        if not training_data.strip():
            raise HTTPException(status_code=400, detail="Training data cannot be empty")
        
        result = update_training_record(
            record_id=record_id,
            user_id=user_id,
            training_data=training_data,
            description=description
        )
        
        logger.info(f"Training record {record_id} updated successfully")
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Record not found: {str(e)}")
        raise HTTPException(status_code=404, detail="Training record not found")
    except RuntimeError as e:
        logger.error(f"Runtime error updating training record: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to update training record at this time")
    except Exception as e:
        logger.error(f"Unexpected error updating training record: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to update training record at this time")


@router.get("/settings/training-record/{record_id}/versions")
async def get_training_record_versions(
    record_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get version history for a training record.
    """
    try:
        # Verify token and get user info
        success, status_code, message, payload = verify_token(credentials.credentials)
        
        if not success or not payload:
            logger.warning("Invalid token attempt in get_training_record_versions")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        user_id = payload.get("user_id")
        
        if not user_id:
            logger.warning("Missing user_id in token payload")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        versions = get_version_history(
            weaviate_data_id=record_id,
            user_id=user_id
        )
        
        logger.info(f"Retrieved {len(versions)} versions for record {record_id}")
        return {
            "success": True,
            "record_id": record_id,
            "versions": versions,
            "total_versions": len(versions)
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Record not found: {str(e)}")
        raise HTTPException(status_code=404, detail="Training record not found")
    except RuntimeError as e:
        logger.error(f"Runtime error getting version history: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to retrieve version history at this time")
    except Exception as e:
        logger.error(f"Unexpected error getting version history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve version history at this time")


@router.post("/settings/training-record/{record_id}/restore/{version_number}")
async def restore_training_record_version(
    record_id: int,
    version_number: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Restore a training record to a previous version.
    """
    try:
        # Verify token and get user info
        success, status_code, message, payload = verify_token(credentials.credentials)
        
        if not success or not payload:
            logger.warning("Invalid token attempt in restore_training_record_version")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        user_id = payload.get("user_id")
        
        if not user_id:
            logger.warning("Missing user_id in token payload")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        result = restore_from_version(
            weaviate_data_id=record_id,
            version_number=version_number,
            user_id=user_id
        )
        
        logger.info(f"Restored record {record_id} to version {version_number}")
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Record or version not found: {str(e)}")
        raise HTTPException(status_code=404, detail="Training record or version not found")
    except RuntimeError as e:
        logger.error(f"Runtime error restoring version: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to restore version at this time")
    except Exception as e:
        logger.error(f"Unexpected error restoring version: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to restore version at this time")
