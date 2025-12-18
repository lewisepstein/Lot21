from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any
import jwt
import os
import logging
from passlib.context import CryptContext
from dotenv import load_dotenv
from service_utils.db_utils.pg_db import PostgresDB
from service_utils.log_management import get_logger

# Set up logging
logger = get_logger(__name__)

# Load environment variables
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token blacklist for logout (in production, use Redis or database)
token_blacklist = set()


def _truncate_password(plain_password: str) -> bytes:
    """
    Truncate password to 72 bytes for bcrypt compatibility.
    
    Args:
        plain_password: Plain text password to truncate
    
    Returns:
        Truncated password as bytes
    """
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return password_bytes


# Helper Functions
def hash_password(plain_password: str) -> str:
    """
    Hash a password for manual use (e.g., creating users).
    
    Args:
        plain_password: Plain text password to hash
    
    Returns:
        Hashed password string
    """
    truncated = _truncate_password(plain_password)
    return pwd_context.hash(truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
    
    Returns:
        True if password matches, False otherwise
    
    Note:
        Bcrypt has a 72-byte limit, so passwords are automatically truncated.
    """
    truncated = _truncate_password(plain_password)
    return pwd_context.verify(truncated, hashed_password)


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
    user = get_user(username)
    if not user:
        return False, 401, "User not found", None
    
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
    except jwt.JWTError:
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
