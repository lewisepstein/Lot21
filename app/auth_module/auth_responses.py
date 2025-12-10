from pydantic import BaseModel

class LoginRequest(BaseModel):
    """
    Request model for user login.
    
    Attributes:
        email (str): The email of the user attempting to log in.
        passwd (str): The password of the user attempting to log in.
    """
    email: str
    passwd: str


class LoginResponse(BaseModel):
    """
    Response model for successful login.
    
    Attributes:
        access_token (str): JWT access token for authenticated requests.
        token_type (str): The type of token, typically 'bearer'.
        expires_in (int): Token expiration time in seconds.
        user (dict): Dictionary containing user information (username, email, full_name).
    """
    access_token: str
    token_type: str
    expires_in: int
    user: dict


class LogoutResponse(BaseModel):
    """
    Response model for successful logout.
    
    Attributes:
        message (str): Confirmation message for the logout action.
        status (str): Status of the logout operation (e.g., 'success').
    """
    message: str
    status: str


class PasswordResetRequest(BaseModel):
    """
    Request model for password reset.
    
    Attributes:
        email (str): User's registered email address.
    """
    email: str


class PasswordResetResponse(BaseModel):
    """
    Response model for password reset request.
    
    Attributes:
        message (str): Confirmation message for the password reset request.
        status (str): Status of the operation.
    """
    message: str
    status: str


class PasswordChangeRequest(BaseModel):
    """
    Request model for password change.
    
    Attributes:
        old_passwd (str): Current password.
        new_passwd (str): New password.
        confirm_new_passwd (str): New password confirmation.
    """
    old_passwd: str
    new_passwd: str
    confirm_new_passwd: str


class PasswordChangeResponse(BaseModel):
    """
    Response model for password change.
    
    Attributes:
        message (str): Confirmation message for the password change.
        status (str): Status of the operation.
    """
    message: str
    status: str
