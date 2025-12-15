from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from auth_module.auth_utils import verify_token
from agent_module.agent_utils import (
    load_training_data_to_weaviate,
    get_training_history,
    delete_training_record,
    update_training_record,
    get_version_history,
    restore_from_version
)

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """
    Render agent settings page.
    Authentication handled by frontend JavaScript.
    """
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
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # Get request data
    data = await request.json()
    
    # TODO: Implement logic to save API credentials to database
    # For now, return success response
    
    return {
        "success": True,
        "message": "API credentials saved successfully"
    }


@router.get("/settings/api")
async def get_api_credentials(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get API credentials status (without revealing actual keys).
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # TODO: Implement logic to check if API credentials exist in database
    
    return {
        "web_search_configured": False,
        "image_gen_configured": False
    }


@router.post("/settings/schedule")
async def save_schedule_settings(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Save scheduling preferences for content generation.
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # Get request data
    data = await request.json()
    
    # TODO: Implement logic to save schedule settings to database
    
    return {
        "success": True,
        "message": "Schedule settings saved successfully"
    }


@router.get("/settings/schedule")
async def get_schedule_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current scheduling preferences.
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # TODO: Implement logic to retrieve schedule settings from database
    
    return {
        "understanding_schedule": "weekly",
        "newsletter_schedule": "weekly",
        "social_schedule": "daily",
        "preferred_time": "09:00",
        "auto_publish": False
    }


@router.post("/settings/content")
async def save_content_settings(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Save content style preferences.
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # Get request data
    data = await request.json()
    
    # TODO: Implement logic to save content settings to database
    
    return {
        "success": True,
        "message": "Content preferences saved successfully"
    }


@router.get("/settings/content")
async def get_content_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current content style preferences.
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # TODO: Implement logic to retrieve content settings from database
    
    return {
        "writing_tone": "professional",
        "target_audience": "general",
        "content_length": "medium",
        "include_images": True,
        "include_sources": True
    }


@router.post("/settings/model")
async def save_model_settings(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Save AI language model preferences.
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # Get request data
    data = await request.json()
    
    # TODO: Implement logic to save model settings to database
    
    return {
        "success": True,
        "message": "Language model saved successfully"
    }


@router.get("/settings/model")
async def get_model_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current AI language model preferences.
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # TODO: Implement logic to retrieve model settings from database
    
    return {
        "language_model": "gpt-4"
    }


@router.post("/settings/image-model")
async def save_image_model_settings(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Save AI image generation model preferences.
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # Get request data
    data = await request.json()
    
    # TODO: Implement logic to save image model settings to database
    
    return {
        "success": True,
        "message": "Image generation model saved successfully"
    }


@router.get("/settings/image-model")
async def get_image_model_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current AI image generation model preferences.
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # TODO: Implement logic to retrieve image model settings from database
    
    return {
        "image_model": "dall-e-3"
    }


@router.get("/settings/training-history")
async def get_training_history_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get training data loading history from weaviate_data table.
    """
    # Verify token
    success, status_code, message, payload = verify_token(credentials.credentials)
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user authentication")
    
    try:
        history = get_training_history(user_id=user_id, limit=50)
        return {"history": history}
        
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error fetching training history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch training history: {str(e)}")


@router.post("/settings/train-model")
async def load_training_data(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Load training data into Weaviate vector database and store metadata in database.
    Chunks the data and stores it with embeddings.
    """
    # Verify token and get user info
    success, status_code, message, payload = verify_token(credentials.credentials)
    
    if not success or not payload:
        raise HTTPException(status_code=status_code, detail=message)
    
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user authentication")
    
    # Get request data
    data = await request.json()
    training_data = data.get("training_data", "")
    collection_name = data.get("collection_name", "training_data")
    description = data.get("description", "")
    
    if not training_data.strip():
        raise HTTPException(status_code=400, detail="Training data cannot be empty")
    
    if not collection_name.strip():
        raise HTTPException(status_code=400, detail="Collection name cannot be empty")
    
    try:
        # Use the utility function to load data into Weaviate and save to database
        result = load_training_data_to_weaviate(
            training_data=training_data,
            collection_name=collection_name,
            user_id=user_id,
            description=description
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading data to Weaviate: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load data to Weaviate: {str(e)}")


@router.delete("/settings/training-record/{record_id}")
async def delete_training_record(
    record_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Delete (soft delete) a training record from the database.
    """
    # Verify token and get user info
    success, status_code, message, payload = verify_token(credentials.credentials)
    
    if not success or not payload:
        raise HTTPException(status_code=status_code, detail=message)
    
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user authentication")
    
    try:
        result = delete_training_record(record_id=record_id, user_id=user_id)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting training record: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete training record: {str(e)}")


@router.put("/settings/training-record/{record_id}")
async def update_training_record_endpoint(
    record_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Update an existing training record with new data.
    """
    # Verify token and get user info
    success, status_code, message, payload = verify_token(credentials.credentials)
    
    if not success or not payload:
        raise HTTPException(status_code=status_code, detail=message)
    
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user authentication")
    
    # Get request data
    data = await request.json()
    training_data = data.get("training_data", "")
    description = data.get("description", "")
    
    if not training_data.strip():
        raise HTTPException(status_code=400, detail="Training data cannot be empty")
    
    try:
        result = update_training_record(
            record_id=record_id,
            user_id=user_id,
            training_data=training_data,
            description=description
        )
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating training record: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update training record: {str(e)}")


@router.get("/settings/training-record/{record_id}/versions")
async def get_training_record_versions(
    record_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get version history for a training record.
    """
    # Verify token and get user info
    success, status_code, message, payload = verify_token(credentials.credentials)
    
    if not success or not payload:
        raise HTTPException(status_code=status_code, detail=message)
    
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user authentication")
    
    try:
        versions = get_version_history(
            weaviate_data_id=record_id,
            user_id=user_id
        )
        return {
            "success": True,
            "record_id": record_id,
            "versions": versions,
            "total_versions": len(versions)
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting version history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get version history: {str(e)}")


@router.post("/settings/training-record/{record_id}/restore/{version_number}")
async def restore_training_record_version(
    record_id: int,
    version_number: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Restore a training record to a previous version.
    """
    # Verify token and get user info
    success, status_code, message, payload = verify_token(credentials.credentials)
    
    if not success or not payload:
        raise HTTPException(status_code=status_code, detail=message)
    
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user authentication")
    
    try:
        result = restore_from_version(
            weaviate_data_id=record_id,
            version_number=version_number,
            user_id=user_id
        )
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error restoring version: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to restore version: {str(e)}")
