from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import timedelta

from auth_module.auth_responses import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    PasswordChangeRequest,
    PasswordChangeResponse
)

from auth_module.auth_utils import (
    authenticate_user,
    create_access_token,
    blacklist_token,
    verify_token,
    get_user_data,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

from validations.auth import (
    PasswordResetValidation,
    PasswordChangeValidation
)

# Create router
router = APIRouter(prefix="/auth", tags=["auth"])

# Security
security = HTTPBearer()


# API Endpoints
@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """
    Login endpoint - authenticates user and returns JWT token.
    
    Args:
        login_data: LoginRequest containing username and password
    
    Returns:
        JSON response with access token and user information
    """
    # Authenticate user
    success, status_code, message, user = authenticate_user(
        login_data.email, 
        login_data.passwd
    )
    
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_success, token_status_code, token_message, access_token = create_access_token(
        data={"email": user["email"]},
        expires_delta=access_token_expires
    )
    
    if not token_success:
        raise HTTPException(status_code=token_status_code, detail=token_message)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
        "user": {
            "id": user["id"],
            "email": user["email"],
            "is_active": user["is_active"]
        }
    }


@router.post("/logout", response_model=LogoutResponse)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout endpoint - invalidates the current JWT token.
    
    Args:
        credentials: Bearer token from Authorization header
    
    Returns:
        JSON response confirming logout
    """
    token = credentials.credentials
    
    # Blacklist token
    success, status_code, message = blacklist_token(token)
    
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    return {
        "message": "Successfully logged out",
        "status": "success"
    }


@router.post("/password-reset", response_model=PasswordResetResponse)
async def password_reset(reset_data: PasswordResetRequest):
    """
    Password reset endpoint - initiates password reset process.
    
    Args:
        reset_data: PasswordResetRequest containing user email
    
    Returns:
        JSON response confirming password reset request
    """
    # Validate request data using Pydantic validation
    try:
        validated_data = PasswordResetValidation(email=reset_data.email)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Check if user exists
    # Note: For security, we return success even if user doesn't exist
    # to prevent email enumeration attacks
    # TODO: Implement actual password reset logic:
    # 1. Check if user exists in database
    # 2. Generate password reset token
    # 3. Send reset email to user
    # 4. Store reset token with expiration
    
    user_success, user_status_code, user_message, user = get_user_data(validated_data.email)
    
    # Always return success to prevent email enumeration
    return {
        "message": "If the email exists, a password reset link has been sent",
        "status": "success"
    }


@router.post("/password-change", response_model=PasswordChangeResponse)
async def password_change(
    change_data: PasswordChangeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Password change endpoint - allows authenticated users to change their password.
    
    Args:
        change_data: PasswordChangeRequest containing old and new passwords
        credentials: Bearer token from Authorization header
    
    Returns:
        JSON response confirming password change
    """
    # Validate request data using Pydantic validation
    try:
        validated_data = PasswordChangeValidation(
            old_passwd=change_data.old_passwd,
            new_passwd=change_data.new_passwd,
            confirm_new_passwd=change_data.confirm_new_passwd
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    token = credentials.credentials
    
    # Verify token
    success, status_code, message, payload = verify_token(token)
    
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # Get user data
    email = payload.get("sub")
    user_success, user_status_code, user_message, user = get_user_data(email)
    
    if not user_success:
        raise HTTPException(status_code=user_status_code, detail=user_message)
    
    # TODO: Implement actual password change logic:
    # 1. Verify old password matches current password in database
    # 2. Hash new password
    # 3. Update password in database
    # 4. Optionally invalidate all existing tokens
    # 5. Send confirmation email
    
    # For now, return success (this will be implemented with database)
    return {
        "message": "Password changed successfully",
        "status": "success"
    }
