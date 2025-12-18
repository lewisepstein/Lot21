from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import timedelta
from typing import Optional

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
    ACCESS_TOKEN_EXPIRE_MINUTES,
    invalidate_all_user_sessions
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
async def login(login_data: LoginRequest, request: Request):
    """
    Login endpoint - authenticates user, creates session, and returns JWT token.
    
    Args:
        login_data: LoginRequest containing username and password
        request: FastAPI Request object for extracting client info
    
    Returns:
        JSON response with access token, session token, and user information
    """
    # Authenticate user
    success, status_code, message, user = authenticate_user(
        login_data.email, 
        login_data.passwd
    )
    
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    # Extract client information
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    
    # Step 1: Create session record BEFORE JWT token (as per flowchart)
    from auth_module.auth_utils import create_session_without_jwt, update_session_with_jwt, delete_session
    session_success, session_status, session_message, session = create_session_without_jwt(
        user_id=user["id"],
        ip_address=client_ip,
        user_agent=user_agent
    )
    
    if not session_success:
        # Session creation failed - redirect to login (NO path in flowchart)
        raise HTTPException(status_code=session_status, detail=session_message)
    
    session_id = session.get("id")
    session_token = session.get("session_token")
    
    # Step 2: Create JWT token only if session creation succeeded
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_success, token_status_code, token_message, access_token = create_access_token(
        data={"email": user["email"], "user_id": user["id"]},
        expires_delta=access_token_expires
    )
    
    if not token_success:
        # JWT creation failed - delete session record and redirect to login
        delete_session(session_id)
        raise HTTPException(status_code=token_status_code, detail=token_message)
    
    # Step 3: Update session table with JWT token hash
    update_success, update_status, update_message = update_session_with_jwt(
        session_id=session_id,
        jwt_token=access_token
    )
    
    if not update_success:
        # Failed to update session with JWT - delete session and redirect to login
        delete_session(session_id)
        raise HTTPException(status_code=update_status, detail=update_message)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
        "session_token": session_token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "is_active": user["is_active"]
        }
    }


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session_token: Optional[str] = None
):
    """
    Logout endpoint - invalidates the current JWT token and session.
    
    Args:
        credentials: Bearer token from Authorization header
        session_token: Optional session token to invalidate
    
    Returns:
        JSON response confirming logout
    """
    token = credentials.credentials
    
    # Blacklist JWT token
    jwt_success, jwt_status_code, jwt_message = blacklist_token(token)
    
    if not jwt_success:
        raise HTTPException(status_code=jwt_status_code, detail=jwt_message)
    
    # Delete session record from sessions table if session_token provided
    if session_token:
        from auth_module.auth_utils import delete_session_by_token
        session_success, session_status, session_message = delete_session_by_token(session_token)
        if not session_success:
            # Log warning but don't fail logout if session deletion fails
            pass
    
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
