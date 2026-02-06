"""Pydantic models for Free Form module API requests and responses."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ProjectCreateRequest(BaseModel):
    """Request model for creating a new project."""
    project_name: str = Field(..., min_length=1, max_length=255, description="Name of the project")
    project_description: Optional[str] = Field(None, max_length=500, description="Description of the project")


class ProjectUpdateRequest(BaseModel):
    """Request model for updating a project."""
    project_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Name of the project")
    project_description: Optional[str] = Field(None, max_length=500, description="Description of the project")
    is_active: Optional[bool] = Field(None, description="Whether the project is active")


class ProjectResponse(BaseModel):
    """Response model for a project."""
    id: int
    project_name: str
    project_description: Optional[str]
    created_by: Optional[int]
    created_on: str
    updated_on: Optional[str]
    is_active: bool


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    project_id: int = Field(..., description="ID of the project/conversation")
    content: str = Field(..., min_length=1, description="Message content")
    content_type: Optional[str] = Field("TEXT", description="Content type (TEXT/IMAGE/MULTIMODAL)")
    attachments: Optional[str] = Field(None, description="JSON string of attachments")


class ChatMessageResponse(BaseModel):
    """Response model for a chat message."""
    id: int
    project_id: int
    role: str
    content: Optional[str]
    content_type: str
    attachments: Optional[str]
    created_on: str


class ChatHistoryResponse(BaseModel):
    """Response model for chat history."""
    messages: List[ChatMessageResponse]
    total: int


class ProjectListResponse(BaseModel):
    """Response model for list of projects."""
    projects: List[ProjectResponse]
    total: int


class AttachmentItem(BaseModel):
    """Model for individual attachment."""
    name: str
    type: str
    size: int
    data: str  # Base64 encoded file content


class ChatCompletionRequest(BaseModel):
    """Request model for chat completion (streaming)."""
    project_id: int
    message: str
    include_history: bool = Field(default=True, description="Include chat history in context")
    attachments: Optional[List[AttachmentItem]] = Field(default=None, description="List of file attachments")
