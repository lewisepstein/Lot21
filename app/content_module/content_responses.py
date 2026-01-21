from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ContentCreateRequest(BaseModel):
    """
    Request model for creating new content.
    """
    category_id: Optional[int] = Field(default=None, description="ID of the category")
    prompt_data: Optional[str] = Field(default=None, description="Input prompt data")
    action: Optional[str] = Field(default=None, description="Action to perform on the content")
    content_type: Optional[str] = Field(default=None, description="Type of content being created")
    generated_content: Optional[str] = Field(default=None, description="AI-generated content output")


class ContentResponse(BaseModel):
    """
    Response model for content operations.
    """
    id: int
    category_id: Optional[int]
    prompt_data: Optional[str]
    generated_content: Optional[str]
    created_on: datetime
    deleted_on: Optional[datetime]
    action: str
    approval_status: str
    approval_status_date: Optional[datetime]
    accuracy: Optional[float]
    comments: Optional[str]
    quarter: Optional[str]
    content_type: Optional[str]

    class Config:
        from_attributes = True


class ContentCreateResponse(BaseModel):
    """
    Response model for content creation.
    """
    message: str
    content: ContentResponse
    prompt_session_id: Optional[str] = Field(default=None, description="UUID for the prompt session if action is NEW")


class AddDraftContentRequest(BaseModel):
    """
    Request model for adding draft content to prompt history.
    """
    prompt_text: str = Field(..., min_length=1, description="The prompt text")
    content_id: Optional[int] = Field(None, description="ID of the content")
    prompt_session_id: Optional[str] = Field(None, description="UUID of the prompt session")
    context_override: Optional[bool] = False


class SaveAsDraftRequest(BaseModel):
    """
    Request model for adding draft content to prompt history.
    """
    prompt_history_id: int = Field(..., gt=0, description="ID of the prompt history record")
    prompt_action: str = Field(default="SAVE_AS_DRAFT", description="Action to perform on the prompt (e.g., SAVE_AS_DRAFT)")
    prompt_name: Optional[str] = Field(default=None, description="Name of the prompt")
    prompt_description: Optional[str] = Field(default=None, description="Description of the prompt")


class PromptHistoryResponse(BaseModel):
    """
    Response model for prompt history.
    """
    id: int
    prompt_session_id: str
    content_id: int
    user_prompt: Optional[str]
    ai_response: Optional[str]
    prompt_type: str
    created_on: datetime
    deleted_on: Optional[datetime]
    prompt_action: Optional[str]
    updated_on: Optional[datetime] = None

    class Config:
        from_attributes = True


class AddDraftContentResponse(BaseModel):
    """
    Response model for adding draft content.
    """
    message: str
    prompt_history: PromptHistoryResponse


class RagRetrieveContextResponse(BaseModel):
    """
    Response model for RAG context retrieval.
    """
    context: str
    prompt_session_id: str