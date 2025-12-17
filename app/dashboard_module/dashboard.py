from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone
import logging

from dashboard_module.dashboard_responses import DashboardResponse
from auth_module.auth_utils import verify_token, get_user_data

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/user", tags=["user"])

# Security
security = HTTPBearer()

# Templates
templates = Jinja2Templates(directory="templates")


# HTML Page Endpoints (Frontend handles auth via JavaScript)
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Render dashboard HTML page. Authentication handled by frontend JavaScript."""
    try:
        return templates.TemplateResponse(
            "dashboard.htm",
            {"request": request}
        )
    except Exception as e:
        logger.error(f"Error loading dashboard page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "dashboard.htm",
            {"request": request}
        )

# API Endpoints
@router.get("/dashboard-data", response_model=DashboardResponse)
async def dashboard_data(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dashboard data API endpoint - returns dashboard data for authenticated user.
    
    Args:
        credentials: Bearer token from Authorization header
    
    Returns:
        JSON response with dashboard information
    """
    try:
        token = credentials.credentials
        
        # Verify token
        success, status_code, message, payload = verify_token(token)
        
        if not success:
            logger.warning("Invalid token attempt in dashboard_data")
            raise HTTPException(status_code=status_code, detail="Authentication failed")
        
        # Get user data
        email = payload.get("email")
        user_success, user_status_code, user_message, user = get_user_data(email)
        
        if not user_success:
            logger.error(f"Failed to get user data for {email}")
            raise HTTPException(status_code=user_status_code, detail="Unable to retrieve user information")
        
        logger.info(f"Dashboard data retrieved for user: {email}")
        
        return {
            "message": "Welcome to your dashboard",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "is_active": user["is_active"]
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "total_items": 42,
                "active_sessions": 3,
                "last_login": datetime.now(timezone.utc).isoformat(),
                "permissions": ["read", "write", "admin"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving dashboard data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to load dashboard data at this time")
