from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class LoginRequestValidation(BaseModel):
    """
    Validation model for user login request.
    Synced with models/users.py (email, passwd fields).
    
    Attributes:
        email (EmailStr): The email of the user attempting to log in.
        passwd (str): The password of the user attempting to log in.
    """
    email: EmailStr = Field(
        ...,
        description="User email for login",
        examples=["user@example.com"]
    )
    passwd: str = Field(
        ...,
        min_length=8,
        max_length=255,
        description="User password (min 8 characters)",
        examples=["SecurePass123!"]
    )
    
    @field_validator("passwd")
    @classmethod
    def validate_passwd(cls, v: str) -> str:
        """Validate password."""
        if not v or not v.strip():
            raise ValueError("Password cannot be empty or whitespace only")
        
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        return v


class UserRegistrationValidation(BaseModel):
    """
    Validation model for user registration (for future use).
    Synced with models/users.py (email, passwd, is_active fields).
    
    Attributes:
        email (EmailStr): User's email address (max 255 chars as per DB).
        passwd (str): User's password (stored hashed, max 255 chars).
        confirm_passwd (str): Password confirmation.
        is_active (bool): User account active status (default: True).
    """
    email: EmailStr = Field(
        ...,
        max_length=255,
        description="Valid email address (unique)",
        examples=["user@example.com"]
    )
    passwd: str = Field(
        ...,
        min_length=8,
        max_length=255,
        description="User password (min 8 characters, will be hashed)",
        examples=["SecurePass123!"]
    )
    confirm_passwd: str = Field(
        ...,
        min_length=8,
        max_length=255,
        description="Password confirmation",
        examples=["SecurePass123!"]
    )
    is_active: bool = Field(
        default=True,
        description="User account active status"
    )
    
    @field_validator("passwd")
    @classmethod
    def validate_passwd_strength(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        
        return v
    
    @field_validator("confirm_passwd")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Validate that passwords match."""
        if "passwd" in info.data and v != info.data["passwd"]:
            raise ValueError("Passwords do not match")
        return v


class PasswordResetValidation(BaseModel):
    """
    Validation model for password reset request (for future use).
    
    Attributes:
        email (EmailStr): User's registered email address.
    """
    email: EmailStr = Field(
        ...,
        description="Registered email address",
        examples=["user@example.com"]
    )


class PasswordChangeValidation(BaseModel):
    """
    Validation model for password change (for future use).
    Synced with models/users.py (passwd field).
    
    Attributes:
        old_passwd (str): Current password.
        new_passwd (str): New password.
        confirm_new_passwd (str): New password confirmation.
    """
    old_passwd: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Current password"
    )
    new_passwd: str = Field(
        ...,
        min_length=8,
        max_length=255,
        description="New password (min 8 characters)"
    )
    confirm_new_passwd: str = Field(
        ...,
        min_length=8,
        max_length=255,
        description="New password confirmation"
    )
    
    @field_validator("new_passwd")
    @classmethod
    def validate_new_passwd(cls, v: str, info) -> str:
        """Validate new password strength and ensure it's different from old."""
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters long")
        
        if "old_passwd" in info.data and v == info.data["old_passwd"]:
            raise ValueError("New password must be different from the old password")
        
        return v
    
    @field_validator("confirm_new_passwd")
    @classmethod
    def new_passwords_match(cls, v: str, info) -> str:
        """Validate that new passwords match."""
        if "new_passwd" in info.data and v != info.data["new_passwd"]:
            raise ValueError("New passwords do not match")
        return v
