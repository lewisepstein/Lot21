from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, Callable
from functools import wraps
import jwt
import os
import secrets
import hashlib
from fastapi import Request
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from dotenv import load_dotenv
from service_utils.db_utils.pg_db import PostgresDB
from service_utils.log_management import get_logger
from service_utils.custom_exceptions.sqlalchemy_custom_exceptions import (
    SQLAlchemyInsertError,
    SQLAlchemyReadError,
    SQLAlchemyUpdateError,
    SQLAlchemyDeleteError
)

# Set up logging
logger = get_logger(__name__)

# Load environment variables
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
SESSION_EXPIRE_MINS = int(os.getenv("SESSION_EXPIRE_MINS"))

MAX_PASSWORD_LENGTH = 64  # safe under 72 bytes
MIN_PASSWORD_LENGTH = 3

# Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Token blacklist for logout (in production, use Redis or database)
token_blacklist = set()


# Decorator for session-based authentication on template routes
def require_session_auth(redirect_url: str = "/"):
    """
    Decorator to require session authentication for template rendering routes.
    Redirects to specified URL if session is invalid or missing.
    
    Args:
        redirect_url: URL to redirect to if authentication fails (default: "/")
    
    Returns:
        Decorated function that checks session authentication
    
    Example:
        @router.get("/dashboard", response_class=HTMLResponse)
        @require_session_auth(redirect_url="/")
        async def dashboard_page(request: Request, session_token: Optional[str] = Cookie(default=None)):
            # This code only runs if session is valid
            return templates.TemplateResponse(request=request, name="dashboard.htm")
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract session_token from kwargs (it should be passed as Cookie parameter)
            session_token = kwargs.get('session_token')
            
            # Extract request from args or kwargs
            request = kwargs.get('request') or (args[0] if args and isinstance(args[0], Request) else None)
            
            if not session_token:
                logger.warning(f"Access attempted without session token to {request.url.path if request else 'unknown'}")
                return RedirectResponse(url=redirect_url, status_code=302)
            
            # Verify session
            success, status_code, message, user = verify_session_auth(session_token)
            
            if not success:
                logger.warning(f"Invalid session attempt: {message} on {request.url.path if request else 'unknown'}")
                return RedirectResponse(url=redirect_url, status_code=302)
            
            # Add user to kwargs for use in the route function
            kwargs['authenticated_user'] = user
            logger.info(f"Authenticated access to {request.url.path if request else 'unknown'} by user: {user.get('email', 'unknown')}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def hash_password(plain_password: str) -> str:
    if not (MIN_PASSWORD_LENGTH <= len(plain_password) <= MAX_PASSWORD_LENGTH):
        raise ValueError(
            f"Password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters"
        )
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if len(plain_password) > MAX_PASSWORD_LENGTH:
        return False
    
    # Check if hashed_password is valid before attempting verification
    if not hashed_password or not isinstance(hashed_password, str):
        logger.error("Invalid hashed_password: empty or not a string")
        return False
    
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification failed: {str(e)}")
        logger.error("Hash format may be invalid or not supported by pwd_context")
        return False


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user from database.
    
    Args:
        username: Email address of the user (used as username)
    
    Returns:
        User dict if found, None otherwise
    """
    try:
        db = PostgresDB()
        users = db.read('users', conditions={'email': username, 'is_active': True})

        print(users, username)
        
        if not users:
            return None
        
        # Return the first user found with hashed_password field mapped from passwd
        user = users[0]
        # Map 'passwd' field to 'hashed_password' for compatibility
        user['hashed_password'] = user.get('passwd')
        return user
        
    except Exception as e:
        logger.error(f"Error retrieving user {username}: {e}")
        return None


def authenticate_user(username: str, password: str) -> Tuple[bool, int, str, Optional[Dict[str, Any]]]:
    """
    Authenticate a user.
    
    Args:
        username: Username to authenticate
        password: Password to verify
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str, user_data: dict or None)
    """

    print(username, password)

    user = get_user(username)

    print(user)

    if not user:
        return False, 401, "User not found", None
    
    # Check if hashed_password exists in user record
    if "hashed_password" not in user or not user["hashed_password"]:
        logger.error(f"User {username} has no hashed_password stored")
        return False, 500, "Authentication configuration error", None
    
    if not verify_password(password, user["hashed_password"]):
        return False, 401, "Incorrect password", None
    
    return True, 200, "Authentication successful", user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> Tuple[bool, int, str, Optional[str]]:
    """
    Create JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Optional expiration time delta
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str, token: str or None)
    """
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return True, 200, "Token created successfully", encoded_jwt
    except Exception as e:
        return False, 500, f"Failed to create token: {str(e)}", None


def verify_token(token: str) -> Tuple[bool, int, str, Optional[Dict[str, Any]]]:
    """
    Verify JWT token and return user info.
    
    Args:
        token: JWT token string
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str, payload: dict or None)
    """
    # Check if token is blacklisted
    if token in token_blacklist:
        return False, 401, "Token has been revoked", None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("email")
        if email is None:
            return False, 401, "Could not validate credentials", None
        return True, 200, "Token verified successfully", payload
    except jwt.ExpiredSignatureError:
        return False, 401, "Token has expired", None
    except jwt.PyJWTError:
        return False, 401, "Invalid token", None


def blacklist_token(token: str) -> Tuple[bool, int, str]:
    """
    Add token to blacklist.
    
    Args:
        token: JWT token to blacklist
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str)
    """
    # First verify token is valid before blacklisting
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_blacklist.add(token)
        return True, 200, "Token blacklisted successfully"
    except jwt.JWTError:
        return False, 401, "Invalid token"


def get_user_data(username: str) -> Tuple[bool, int, str, Optional[Dict[str, Any]]]:
    """
    Get user data by username.
    
    Args:
        username: Username to retrieve
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str, user_data: dict or None)
    """
    user = get_user(username)
    if not user:
        return False, 404, "User not found", None
    return True, 200, "User found", user

# Session Management Functions
def _hash_token(token: str) -> str:
    """
    Create a hash of the JWT token for secure storage.
    
    Args:
        token: JWT token string
    
    Returns:
        SHA256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(
    user_id: int,
    jwt_token: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Tuple[bool, int, str, Optional[Dict[str, Any]]]:
    """
    Create a new session for authenticated user.
    
    Args:
        user_id: User ID
        jwt_token: JWT access token
        ip_address: Client IP address (optional)
        user_agent: Client user agent string (optional)
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str, session_data: dict or None)
    """
    try:
        db = PostgresDB()
        
        # Generate unique session token
        session_token = secrets.token_urlsafe(32)
        
        # Hash the JWT token for storage
        jwt_token_hash = _hash_token(jwt_token)
        
        # Calculate expiration time - use the same pattern as other utils
        expires_at = datetime.now(datetime.now().astimezone().tzinfo) + timedelta(minutes=SESSION_EXPIRE_MINS)
        
        # Create session record
        session_data = {
            "user_id": user_id,
            "session_token": session_token,
            "jwt_token_hash": jwt_token_hash,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "is_active": True,
            "expires_at": expires_at
        }
        
        created_session = db.create("sessions", session_data)
        
        if not created_session:
            logger.error(f"Failed to create session for user {user_id}")
            return False, 500, "Failed to create session", None
        
        logger.info(f"Session created for user {user_id}: {session_token[:10]}...")
        return True, 200, "Session created successfully", created_session
        
    except Exception as e:
        logger.error(f"Error creating session for user {user_id}: {str(e)}", exc_info=True)
        return False, 500, f"Error creating session: {str(e)}", None


def create_session_without_jwt(
    user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Tuple[bool, int, str, Optional[Dict[str, Any]]]:
    """
    Create a new session WITHOUT JWT token (Step 1 in login flow).
    JWT will be added later via update_session_with_jwt.
    
    Args:
        user_id: User ID
        ip_address: Client IP address (optional)
        user_agent: Client user agent string (optional)
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str, session_data: dict or None)
    """
    try:
        db = PostgresDB()
        
        # Generate unique session token
        session_token = secrets.token_urlsafe(32)
        
        # Calculate expiration time
        expires_at = datetime.now(datetime.now().astimezone().tzinfo) + timedelta(minutes=SESSION_EXPIRE_MINS)
        
        # Create session record without JWT token hash
        session_data = {
            "user_id": user_id,
            "session_token": session_token,
            "jwt_token_hash": None,  # Will be updated after JWT creation
            "ip_address": ip_address,
            "user_agent": user_agent,
            "is_active": True,
            "expires_at": expires_at
        }
        
        created_session = db.create("sessions", session_data)
        
        if not created_session:
            logger.error(f"Failed to create session for user {user_id}")
            return False, 500, "Unable to create session. Please try again.", None
        
        logger.info(f"Session created (without JWT) for user {user_id}: {session_token[:10]}...")
        return True, 200, "Session created successfully", created_session
        
    except SQLAlchemyInsertError as e:
        logger.error(f"Database insert error creating session for user {user_id}: {str(e)}", exc_info=True)
        return False, 500, "Unable to create session. Please try again.", None
    except Exception as e:
        logger.error(f"Unexpected error creating session for user {user_id}: {str(e)}", exc_info=True)
        return False, 500, "Unable to create session. Please try again.", None


def update_session_with_jwt(
    session_id: int,
    jwt_token: str
) -> Tuple[bool, int, str]:
    """
    Update session record with JWT token hash (Step 2 in login flow).
    
    Args:
        session_id: Session ID to update
        jwt_token: JWT access token to hash and store
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str)
    """
    try:
        db = PostgresDB()
        
        # Hash the JWT token for storage
        jwt_token_hash = _hash_token(jwt_token)
        
        # Update session with JWT token hash
        db.update("sessions", 
                 {"jwt_token_hash": jwt_token_hash},
                 {"id": session_id})
        
        logger.info(f"Session {session_id} updated with JWT token hash")
        return True, 200, "Session updated successfully"
        
    except SQLAlchemyUpdateError as e:
        logger.error(f"Database update error for session {session_id}: {str(e)}", exc_info=True)
        return False, 500, "Unable to update session. Please try logging in again."
    except Exception as e:
        logger.error(f"Unexpected error updating session {session_id} with JWT: {str(e)}", exc_info=True)
        return False, 500, "Unable to update session. Please try logging in again."


def delete_session(session_id: int) -> Tuple[bool, int, str]:
    """
    Delete a session record from database.
    
    Args:
        session_id: Session ID to delete
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str)
    """
    try:
        db = PostgresDB()
        
        # Delete session record
        db.delete("sessions", conditions={"id": session_id})
        
        logger.info(f"Session {session_id} deleted from database")
        return True, 200, "Session deleted successfully"
        
    except SQLAlchemyDeleteError as e:
        logger.error(f"Database delete error for session {session_id}: {str(e)}", exc_info=True)
        return False, 500, "Unable to delete session. Please try again."
    except Exception as e:
        logger.error(f"Unexpected error deleting session {session_id}: {str(e)}", exc_info=True)
        return False, 500, "Unable to delete session. Please try again."


def delete_session_by_token(session_token: str) -> Tuple[bool, int, str]:
    """
    Delete a session record by session token (used in logout).
    
    Args:
        session_token: Session token to delete
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str)
    """
    try:
        db = PostgresDB()
        
        # Delete session record
        db.delete("sessions", conditions={"session_token": session_token})
        
        logger.info(f"Session deleted: {session_token[:10]}...")
        return True, 200, "Session deleted successfully"
        
    except SQLAlchemyDeleteError as e:
        logger.error(f"Database delete error for session token: {str(e)}", exc_info=True)
        return False, 500, "Unable to delete session. Please try again."
    except Exception as e:
        logger.error(f"Unexpected error deleting session by token: {str(e)}", exc_info=True)
        return False, 500, "Unable to delete session. Please try again."


def verify_session(session_token: str) -> Tuple[bool, int, str, Optional[Dict[str, Any]]]:
    """
    Verify a session token and return session data.
    
    Args:
        session_token: Session token to verify
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str, session_data: dict or None)
    """
    try:
        db = PostgresDB()
        
        # Retrieve session
        sessions = db.read("sessions", conditions={
            "session_token": session_token,
            "is_active": True
        })
        
        if not sessions or len(sessions) == 0:
            logger.warning(f"Session not found or inactive: {session_token[:10]}...")
            return False, 401, "Invalid or expired session", None
        
        session = sessions[0]
        
        # Check if session has expired
        expires_at = session.get("expires_at")
        if expires_at and datetime.now(datetime.now().astimezone().tzinfo) > expires_at:
            # Deactivate expired session
            db.update("sessions", {"is_active": False}, {"id": session["id"]})
            logger.warning(f"Session expired: {session_token[:10]}...")
            return False, 401, "Session has expired", None
        
        # Update last activity
        db.update("sessions", {
            "last_activity": datetime.now(datetime.now().astimezone().tzinfo)
        }, {"id": session["id"]})
        
        logger.info(f"Session verified for user {session['user_id']}")
        return True, 200, "Session verified successfully", session
        
    except SQLAlchemyReadError as e:
        logger.error(f"Database read error verifying session: {str(e)}", exc_info=True)
        return False, 500, "Unable to verify session. Please try logging in again.", None
    except SQLAlchemyUpdateError as e:
        logger.error(f"Database update error in session verification: {str(e)}", exc_info=True)
        return False, 500, "Unable to verify session. Please try logging in again.", None
    except Exception as e:
        logger.error(f"Unexpected error verifying session: {str(e)}", exc_info=True)
        return False, 500, "Unable to verify session. Please try logging in again.", None


def invalidate_session(session_token: str) -> Tuple[bool, int, str]:
    """
    Invalidate a session (logout).
    
    Args:
        session_token: Session token to invalidate
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str)
    """
    try:
        db = PostgresDB()
        
        # Update session to inactive
        db.update("sessions", {
            "is_active": False
        }, {"session_token": session_token})
        
        logger.info(f"Session invalidated: {session_token[:10]}...")
        return True, 200, "Session invalidated successfully"
        
    except SQLAlchemyUpdateError as e:
        logger.error(f"Database update error invalidating session: {str(e)}", exc_info=True)
        return False, 500, "Unable to invalidate session. Please try again."
    except Exception as e:
        logger.error(f"Unexpected error invalidating session: {str(e)}", exc_info=True)
        return False, 500, "Unable to invalidate session. Please try again."


def invalidate_all_user_sessions(user_id: int) -> Tuple[bool, int, str]:
    """
    Invalidate all sessions for a user (e.g., on password change).
    
    Args:
        user_id: User ID whose sessions to invalidate
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str)
    """
    try:
        db = PostgresDB()
        
        # Update all user sessions to inactive
        db.update("sessions", {
            "is_active": False
        }, {"user_id": user_id})
        
        logger.info(f"All sessions invalidated for user {user_id}")
        return True, 200, "All sessions invalidated successfully"
        
    except SQLAlchemyUpdateError as e:
        logger.error(f"Database update error invalidating user {user_id} sessions: {str(e)}", exc_info=True)
        return False, 500, "Unable to invalidate sessions. Please try again."
    except Exception as e:
        logger.error(f"Unexpected error invalidating user sessions: {str(e)}", exc_info=True)
        return False, 500, "Unable to invalidate sessions. Please try again."


def verify_session_auth(session_token: str) -> Tuple[bool, int, str, Optional[Dict[str, Any]]]:
    """
    Verify session and return authenticated user data.
    This is the main function to use for session-based authentication.
    
    Args:
        session_token: Session token from client
    
    Returns:
        Tuple of (success: bool, status_code: int, message: str, user_data: dict or None)
    """
    # Verify session
    session_success, session_status, session_message, session = verify_session(session_token)
    
    if not session_success:
        return False, session_status, session_message, None
    
    # Get user data
    user_id = session.get("user_id")
    if not user_id:
        logger.error("Session missing user_id")
        return False, 500, "Invalid session data", None
    
    try:
        db = PostgresDB()
        users = db.read("users", conditions={"id": user_id, "is_active": True})
        
        if not users or len(users) == 0:
            logger.warning(f"User {user_id} not found or inactive")
            return False, 403, "User account not found or inactive", None
        
        user = users[0]
        logger.info(f"Session authentication successful for user: {user['email']}")
        return True, 200, "Authentication successful", user
        
    except Exception as e:
        logger.error(f"Error retrieving user data: {str(e)}", exc_info=True)
        return False, 500, f"Error retrieving user: {str(e)}", None
