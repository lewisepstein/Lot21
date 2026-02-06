"""Utility functions for Free Form AI module."""

import os
import io
import base64
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from google import genai as genai_new
from google.genai import types
import PyPDF2
import docx
import openpyxl

from service_utils.db_utils.pg_db import PostgresDB
from service_utils.log_management import get_logger
from service_utils.helpers import convert_datetime_to_formatted_string

load_dotenv()

logger = get_logger(__name__)


def format_project_dict(project: Dict) -> Dict:
    """Convert datetime objects to ISO strings in project dict."""
    formatted = project.copy()
    if formatted.get("created_on"):
        formatted["created_on"] = formatted["created_on"].isoformat() if hasattr(formatted["created_on"], 'isoformat') else formatted["created_on"]
    if formatted.get("updated_on"):
        formatted["updated_on"] = formatted["updated_on"].isoformat() if hasattr(formatted["updated_on"], 'isoformat') else formatted["updated_on"]
    if formatted.get("deleted_on"):
        formatted["deleted_on"] = formatted["deleted_on"].isoformat() if hasattr(formatted["deleted_on"], 'isoformat') else formatted["deleted_on"]
    return formatted


def format_chat_dict(chat: Dict) -> Dict:
    """Convert datetime objects to ISO strings in chat dict."""
    formatted = chat.copy()
    if formatted.get("created_on"):
        formatted["created_on"] = formatted["created_on"].isoformat() if hasattr(formatted["created_on"], 'isoformat') else formatted["created_on"]
    if formatted.get("deleted_on"):
        formatted["deleted_on"] = formatted["deleted_on"].isoformat() if hasattr(formatted["deleted_on"], 'isoformat') else formatted["deleted_on"]
    return formatted

# Configure Gemini API for text
GEMINI_API_KEY = os.getenv("GEMINI_TEXT_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Use gemini-3-flash-preview to match other modules
    FREEFORM_MODEL_ID = "gemini-3-flash-preview"
    logger.info(f"Free Form module using text model: {FREEFORM_MODEL_ID}")
else:
    logger.warning("GEMINI_TEXT_API_KEY not set - Free Form AI will not work")

# Configure Gemini API for image generation
GEMINI_IMAGE_API_KEY = os.getenv("GEMINI_IMAGE_API_KEY")
IMAGE_MODEL_ID = os.getenv("IMAGE_MODEL_ID")

if GEMINI_IMAGE_API_KEY and IMAGE_MODEL_ID:
    try:
        image_client = genai_new.Client(
            api_key=GEMINI_IMAGE_API_KEY,
            http_options={"api_version": "v1beta"}
        )
        logger.info(f"Free Form module using image model: {IMAGE_MODEL_ID}")
    except Exception as e:
        logger.error(f"Failed to initialize image client: {str(e)}")
        image_client = None
else:
    logger.warning("GEMINI_IMAGE_API_KEY or IMAGE_MODEL_ID not set - Image generation will not work")
    image_client = None


# ============= IMAGE GENERATION HELPERS =============

def detect_image_request(message: str) -> bool:
    """Detect if user is requesting an image generation."""
    import re

    message_lower = message.lower().strip()

    # Check for explicit exact phrases first
    exact_phrases = [
        "generate image", "generate an image", "generate image of", "generate image for",
        "create image", "create an image", "create image of", "create image for",
        "make image", "make an image", "make image of", "make image for",
        "generate picture", "generate a picture", "generate picture of", "generate picture for",
        "create picture", "create a picture", "create picture of", "create picture for",
        "make picture", "make a picture", "make picture of", "make picture for",
        "generate photo", "generate a photo", "generate photo of", "generate photo for",
        "create photo", "create a photo", "create photo of", "create photo for",
        "make photo", "make a photo", "make photo of", "make photo for",
        "show me an image of", "show me a picture of", "show me a photo of",
        "show image", "show picture", "show photo",
        "draw me", "draw an", "draw a", "sketch a", "sketch an",
        "visualize this", "visualize a", "visualize an",
        "illustration of", "illustrate a", "illustrate an",
        "generate visual", "create visual", "make visual",
        "design an image", "design a picture", "design a visual",
        "i want an image", "i want a picture", "i want a photo",
        "i need an image", "i need a picture", "i need a photo",
        "can you generate an image", "can you create an image", "can you make an image"
    ]

    if any(phrase in message_lower for phrase in exact_phrases):
        return True

    # Check for flexible patterns like "generate [any words] image"
    action_words = ["generate", "create", "make", "produce", "design", "build"]
    image_words = ["image", "picture", "photo", "visual", "illustration", "graphic"]

    # Pattern: action word followed by up to 3 words, then image word
    for action in action_words:
        for image_word in image_words:
            # Match patterns like "generate new image", "create a new picture", etc.
            pattern = rf"\b{action}\s+(?:\w+\s+){{0,3}}{image_word}\b"
            if re.search(pattern, message_lower):
                return True

    return False


def generate_image(prompt: str, context: Optional[str] = None) -> Optional[str]:
    """Generate an image using Gemini Image API and return data URL."""
    logger.info("=== generate_image() called ===")
    logger.info(f"Image client available: {image_client is not None}")
    logger.info(f"IMAGE_MODEL_ID: {IMAGE_MODEL_ID}")

    if not image_client or not IMAGE_MODEL_ID:
        logger.error("Image generation requested but image client not configured")
        logger.error(f"image_client is None: {image_client is None}")
        logger.error(f"IMAGE_MODEL_ID is None: {IMAGE_MODEL_ID is None}")
        return None

    try:
        # For image generation, use only the user's prompt without context
        # This prevents chat history text from appearing in the generated image
        full_prompt = prompt

        # Clean up the prompt to remove image generation keywords
        # Keep only the description of what to generate
        clean_prompt = prompt.lower()
        keywords_to_remove = [
            "generate image of ", "generate an image of ", "generate image for ",
            "create image of ", "create an image of ", "create image for ",
            "make image of ", "make an image of ", "make image for ",
            "draw ", "draw an ", "draw a ",
            "generate picture of ", "create picture of ", "make picture of ",
            "show me an image of ", "show me a picture of ",
            "generate it", "create it", "make it"
        ]

        for keyword in keywords_to_remove:
            if clean_prompt.startswith(keyword):
                full_prompt = prompt[len(keyword):].strip()
                break

        logger.info(f"Clean image prompt: {full_prompt[:200]}...")
        logger.info(f"Calling Gemini Image API with model: {IMAGE_MODEL_ID}")

        # Generate image
        parts = [types.Part.from_text(text=full_prompt)]
        resp = image_client.models.generate_content(
            model=IMAGE_MODEL_ID,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
        )

        logger.info(f"API response received: {resp is not None}")

        if not resp or not getattr(resp, "candidates", None):
            logger.warning("Image generation: No candidates in response")
            return None

        logger.info(f"Number of candidates: {len(resp.candidates)}")

        # Extract image data
        for i, part in enumerate(resp.candidates[0].content.parts):
            logger.info(f"Part {i}: has inline_data={hasattr(part, 'inline_data')}, has image={hasattr(part, 'image')}")

            if hasattr(part, "inline_data") and part.inline_data:
                # Get mime type from inline_data, default to image/png
                mime_type = getattr(part.inline_data, 'mime_type', 'image/png')
                # Convert image bytes to base64 data URL
                image_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                data_url = f"data:{mime_type};base64,{image_b64}"
                logger.info(f"Image generated successfully via inline_data (mime: {mime_type})")
                return data_url
            if hasattr(part, "image") and part.image:
                # Convert image bytes to base64 data URL
                image_b64 = base64.b64encode(part.image.image_bytes).decode("utf-8")
                data_url = f"data:image/png;base64,{image_b64}"
                logger.info(f"Image generated successfully via image.image_bytes")
                return data_url

        logger.warning("Image generation: No image data found in response parts")
        return None

    except Exception as e:
        logger.error(f"Error generating image: {str(e)}", exc_info=True)
        return None


# ============= PROJECT MANAGEMENT =============

def create_project(
    project_name: str,
    created_by: int,
    project_description: Optional[str] = None
) -> Dict:
    """Create a new Free Form project."""
    try:
        db = PostgresDB()

        # Prepare project data
        project_data = {
            "project_name": project_name,
            "project_description": project_description,
            "created_by": created_by,
            "is_active": True
        }

        # Create project
        new_project = db.create("freeform_projects", project_data)

        logger.info(f"Created Free Form project: {project_name} (ID: {new_project['id']})")
        return format_project_dict(new_project)

    except Exception as e:
        logger.error(f"Error creating project: {str(e)}", exc_info=True)
        raise


def get_user_projects(user_id: int, include_inactive: bool = False) -> Tuple[List[Dict], int]:
    """Get all projects for a user."""
    try:
        db = PostgresDB()

        # Build conditions
        conditions = {
            "created_by": user_id,
            "deleted_on": None
        }

        if not include_inactive:
            conditions["is_active"] = True

        # Get projects with ordering
        projects = db.read(
            "freeform_projects",
            conditions=conditions,
            order_by=[("updated_on", False), ("created_on", False)]  # False = DESC
        )

        # Format datetime fields
        formatted_projects = [format_project_dict(p) for p in projects]
        total = len(formatted_projects)

        logger.info(f"Retrieved {total} projects for user {user_id}")
        return formatted_projects, total

    except Exception as e:
        logger.error(f"Error retrieving projects: {str(e)}", exc_info=True)
        raise


def get_project_by_id(project_id: int) -> Optional[Dict]:
    """Get a project by ID."""
    try:
        db = PostgresDB()

        projects = db.read(
            "freeform_projects",
            conditions={
                "id": project_id,
                "deleted_on": None
            }
        )

        if projects:
            return format_project_dict(projects[0])
        return None

    except Exception as e:
        logger.error(f"Error retrieving project {project_id}: {str(e)}", exc_info=True)
        raise


def update_project(
    project_id: int,
    project_name: Optional[str] = None,
    project_description: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Dict:
    """Update a project."""
    try:
        db = PostgresDB()

        # Check if project exists
        existing = get_project_by_id(project_id)
        if not existing:
            raise ValueError(f"Project {project_id} not found")

        # Build update data (only include non-None values)
        update_data = {}
        if project_name is not None:
            update_data["project_name"] = project_name
        if project_description is not None:
            update_data["project_description"] = project_description
        if is_active is not None:
            update_data["is_active"] = is_active

        if not update_data:
            return existing  # Nothing to update

        # Update project
        updated_projects = db.update(
            "freeform_projects",
            update_data,
            {"id": project_id}
        )

        if updated_projects:
            # Convert Row to dict
            updated = dict(updated_projects[0])
            logger.info(f"Updated project {project_id}")
            return format_project_dict(updated)

        return format_project_dict(existing)

    except Exception as e:
        logger.error(f"Error updating project {project_id}: {str(e)}", exc_info=True)
        raise


def delete_project(project_id: int) -> None:
    """Soft delete a project."""
    try:
        db = PostgresDB()

        # Check if project exists
        existing = get_project_by_id(project_id)
        if not existing:
            raise ValueError(f"Project {project_id} not found")

        # Soft delete by setting deleted_on
        db.update(
            "freeform_projects",
            {"deleted_on": datetime.now()},
            {"id": project_id}
        )

        logger.info(f"Deleted project {project_id}")

    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}", exc_info=True)
        raise


# ============= CHAT MANAGEMENT =============

def save_chat_message(
    project_id: int,
    role: str,
    content: str,
    content_type: str = "TEXT",
    attachments: Optional[str] = None
) -> Dict:
    """Save a chat message to the database."""
    try:
        db = PostgresDB()

        # Validate role
        valid_roles = ["USER", "ASSISTANT", "SYSTEM"]
        if role not in valid_roles:
            raise ValueError(f"Invalid role: {role}")

        # Validate content type
        valid_types = ["TEXT", "IMAGE", "MULTIMODAL"]
        if content_type not in valid_types:
            raise ValueError(f"Invalid content type: {content_type}")

        # Prepare message data
        message_data = {
            "project_id": project_id,
            "role": role,
            "content": content,
            "content_type": content_type,
            "attachments": attachments
        }

        # Create message
        new_message = db.create("freeform_chat", message_data)

        logger.info(f"Saved chat message for project {project_id}")
        return format_chat_dict(new_message)

    except Exception as e:
        logger.error(f"Error saving chat message: {str(e)}", exc_info=True)
        raise


def get_chat_history(
    project_id: int,
    limit: Optional[int] = None
) -> Tuple[List[Dict], int]:
    """Get chat history for a project."""
    try:
        db = PostgresDB()

        # Get messages
        messages = db.read(
            "freeform_chat",
            conditions={
                "project_id": project_id,
                "deleted_on": None
            },
            order_by=[("created_on", True)],  # True = ASC (oldest first)
            limit=limit
        )

        # Format datetime fields
        formatted_messages = [format_chat_dict(m) for m in messages]
        total = len(formatted_messages)

        logger.info(f"Retrieved {total} messages for project {project_id}")
        return formatted_messages, total

    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}", exc_info=True)
        raise


# ============= AI INTEGRATION =============

def extract_pdf_text(decoded_data: bytes, file_name: str) -> str:
    """Extract text content from a PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(decoded_data))
        pages_text = []
        for i, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text and page_text.strip():
                pages_text.append(f"[Page {i + 1}]\n{page_text.strip()}")
        if pages_text:
            return f"--- File: {file_name} (PDF - {len(pdf_reader.pages)} pages) ---\n" + "\n\n".join(pages_text) + "\n"
        else:
            return f"[PDF file attached: {file_name} - Could not extract text (may be scanned/image-based)]"
    except Exception as e:
        logger.error(f"Error extracting PDF text from {file_name}: {str(e)}")
        return f"[PDF file attached: {file_name} - Error extracting text]"


def extract_docx_text(decoded_data: bytes, file_name: str) -> str:
    """Extract text content from a Word .docx file."""
    try:
        document = docx.Document(io.BytesIO(decoded_data))
        parts = []

        # Extract paragraphs
        for para in document.paragraphs:
            if para.text.strip():
                parts.append(para.text.strip())

        # Extract tables
        for table_idx, table in enumerate(document.tables):
            table_rows = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_rows.append("\t".join(row_data))
            if table_rows:
                parts.append(f"\n[Table {table_idx + 1}]\n" + "\n".join(table_rows))

        if parts:
            return f"--- File: {file_name} (Word Document) ---\n" + "\n".join(parts) + "\n"
        else:
            return f"[Word document attached: {file_name} - No text content found]"
    except Exception as e:
        logger.error(f"Error extracting DOCX text from {file_name}: {str(e)}")
        return f"[Word document attached: {file_name} - Error extracting text]"


def extract_excel_text(decoded_data: bytes, file_name: str) -> str:
    """Extract text content from an Excel .xlsx file."""
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(decoded_data), read_only=True, data_only=True)
        sheets_text = []

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            rows_text = []
            for row in sheet.iter_rows(values_only=True):
                row_values = [str(cell) if cell is not None else "" for cell in row]
                # Skip completely empty rows
                if any(v.strip() for v in row_values):
                    rows_text.append("\t".join(row_values))
            if rows_text:
                sheets_text.append(f"[Sheet: {sheet_name}]\n" + "\n".join(rows_text))

        workbook.close()

        if sheets_text:
            return f"--- File: {file_name} (Excel - {len(workbook.sheetnames)} sheets) ---\n" + "\n\n".join(sheets_text) + "\n"
        else:
            return f"[Excel file attached: {file_name} - No data found]"
    except Exception as e:
        logger.error(f"Error extracting Excel data from {file_name}: {str(e)}")
        return f"[Excel file attached: {file_name} - Error extracting data]"


MAX_EXTRACTED_TEXT_LENGTH = 50000  # Limit to avoid exceeding AI token limits


def process_text_attachments(attachments: List[Dict]) -> str:
    """
    Process text-based attachments and extract their content.
    Supports: TXT, JSON, CSV, PDF, DOCX, XLSX files.
    Returns a string with all extracted text content.
    """
    if not attachments:
        return ""

    extracted_texts = []

    for att in attachments:
        # Handle both dict and Pydantic model
        file_type = att.type if hasattr(att, 'type') else att.get("type", "")
        file_name = att.name if hasattr(att, 'name') else att.get("name", "")
        file_data = att.data if hasattr(att, 'data') else att.get("data", "")

        try:
            # Skip image files (they're handled separately in multimodal generation)
            if file_type.startswith("image/"):
                continue

            # Decode base64 data
            decoded_data = base64.b64decode(file_data)

            # Handle text files
            if file_type.startswith("text/") or file_name.endswith(".txt"):
                text_content = decoded_data.decode("utf-8", errors="ignore")
                extracted_texts.append(f"--- File: {file_name} ---\n{text_content}\n")

            # Handle JSON files
            elif file_type == "application/json" or file_name.endswith(".json"):
                text_content = decoded_data.decode("utf-8", errors="ignore")
                extracted_texts.append(f"--- File: {file_name} (JSON) ---\n{text_content}\n")

            # Handle CSV files
            elif file_type == "text/csv" or file_name.endswith(".csv"):
                text_content = decoded_data.decode("utf-8", errors="ignore")
                extracted_texts.append(f"--- File: {file_name} (CSV) ---\n{text_content}\n")

            # Handle PDF files
            elif file_type == "application/pdf" or file_name.endswith(".pdf"):
                extracted_texts.append(extract_pdf_text(decoded_data, file_name))

            # Handle Word documents (.docx)
            elif file_name.endswith(".docx") or file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                extracted_texts.append(extract_docx_text(decoded_data, file_name))

            # Handle legacy Word documents (.doc)
            elif file_name.endswith(".doc"):
                file_size = att.size if hasattr(att, 'size') else att.get('size', 0)
                extracted_texts.append(f"[Word document attached: {file_name} - {file_size} bytes. Note: Legacy .doc format is not supported, please convert to .docx]")

            # Handle Excel files (.xlsx)
            elif file_name.endswith(".xlsx") or file_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                extracted_texts.append(extract_excel_text(decoded_data, file_name))

            # Handle legacy Excel files (.xls)
            elif file_name.endswith(".xls"):
                file_size = att.size if hasattr(att, 'size') else att.get('size', 0)
                extracted_texts.append(f"[Excel file attached: {file_name} - {file_size} bytes. Note: Legacy .xls format is not supported, please convert to .xlsx]")

            else:
                file_size = att.size if hasattr(att, 'size') else att.get('size', 0)
                extracted_texts.append(f"[File attached: {file_name} - {file_size} bytes]")

        except Exception as e:
            logger.error(f"Error processing attachment {file_name}: {str(e)}")
            extracted_texts.append(f"[Error processing file: {file_name}]")

    result = "\n".join(extracted_texts)

    # Truncate if too long to avoid exceeding AI token limits
    if len(result) > MAX_EXTRACTED_TEXT_LENGTH:
        result = result[:MAX_EXTRACTED_TEXT_LENGTH] + "\n\n[... Content truncated due to length ...]"
        logger.warning(f"Extracted text truncated from {len(result)} to {MAX_EXTRACTED_TEXT_LENGTH} characters")

    return result


def clean_markdown_formatting(text: str) -> str:
    """
    Remove markdown formatting from text to produce clean plain text.
    Removes headers (##), horizontal rules (---), bullet points, etc.
    """
    import re

    if not text:
        return text

    # Remove markdown headers (## Header, ### Header, etc.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove horizontal rules (---, ***, ___)
    text = re.sub(r'^[\-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Remove bold/italic markers (**text**, __text__, *text*, _text_)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # Remove bullet point markers (-, *, +)
    text = re.sub(r'^[\-\*\+]\s+', '', text, flags=re.MULTILINE)

    # Remove numbered list markers (1., 2., etc.)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)

    # Remove code block markers (```, ~~~)
    text = re.sub(r'^```[\w]*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^~~~[\w]*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^~~~\s*$', '', text, flags=re.MULTILINE)

    # Remove inline code markers (`code`)
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Remove link formatting [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove excessive blank lines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Clean up any remaining whitespace issues
    text = text.strip()

    return text


def generate_ai_response(
    user_message: str,
    chat_history: Optional[List[Dict]] = None,
    attachments: Optional[List[Dict]] = None
) -> Tuple[str, Optional[str], str]:
    """
    Generate AI response using Gemini.
    Returns tuple of (response_text, image_base64, content_type)
    content_type is one of: "TEXT", "IMAGE", "MULTIMODAL"
    """
    try:
        # Check if user is requesting an image
        is_image_request = detect_image_request(user_message)
        logger.info(f"Message: '{user_message[:100]}...' | Image request detected: {is_image_request}")

        # Check if user has attached files
        has_attachments = attachments and len(attachments) > 0
        logger.info(f"Has attachments: {has_attachments}")

        # Build context from chat history
        context_str = ""
        if chat_history:
            recent_history = chat_history[-5:] if len(chat_history) > 5 else chat_history
            context_parts = []
            for msg in recent_history:
                role = msg.get("role", "USER")
                content = msg.get("content", "")
                if role == "USER":
                    context_parts.append(f"User: {content}")
                elif role == "ASSISTANT":
                    context_parts.append(f"Assistant: {content}")
            context_str = "\n".join(context_parts)

        # If image requested, generate image
        if is_image_request:
            logger.info("=== IMAGE GENERATION PATH ===")

            if not image_client:
                logger.error("Image client is not initialized")
                return (
                    "Image generation is not configured. Please contact administrator.",
                    None,
                    "TEXT"
                )

            logger.info(f"Image client is available. Generating image for: {user_message[:100]}...")
            image_b64 = generate_image(user_message, context_str)

            if image_b64:
                logger.info("Image generated successfully, returning to user")
                return (
                    "",  # Empty text - just show the image
                    image_b64,
                    "IMAGE"  # Changed from MULTIMODAL to IMAGE since we're only showing image
                )
            else:
                logger.error("Image generation returned None")
                return (
                    "I'm sorry, I encountered an error while generating the image. Please try again.",
                    None,
                    "TEXT"
                )

        # Otherwise, generate text response
        if not GEMINI_API_KEY:
            return (
                "AI service is not configured. Please contact administrator.",
                None,
                "TEXT"
            )

        # Initialize the model
        model = genai.GenerativeModel(FREEFORM_MODEL_ID)

        # Build conversation history for context
        conversation_parts = []

        if chat_history:
            # Add previous messages for context (limit to last 10 messages to avoid token limits)
            recent_history = chat_history[-10:] if len(chat_history) > 10 else chat_history

            for msg in recent_history:
                role = msg.get("role", "USER")
                content = msg.get("content", "")

                if role == "USER":
                    conversation_parts.append(f"User: {content}")
                elif role == "ASSISTANT":
                    conversation_parts.append(f"Assistant: {content}")

        # Process attachments to add context
        attachment_context = ""
        if attachments:
            attachment_context = process_text_attachments(attachments)
            if attachment_context:
                conversation_parts.append(f"[Attached files content]:\n{attachment_context}")

        # Add the current user message
        conversation_parts.append(f"User: {user_message}")

        # Create the full prompt
        full_prompt = "\n\n".join(conversation_parts)

        # System instruction for free-form mode
        system_instruction = """You are a helpful, creative AI assistant with no restrictions on topics or scope.
You can help with:
- Content generation (blogs, articles, posts, emails, etc.)
- Image descriptions and creative prompts
- Research and information gathering
- Summarization and analysis
- Creative writing and brainstorming
- Technical questions and coding
- General questions and conversations

IMPORTANT: Provide your responses in clean, plain text format WITHOUT using markdown formatting.
Do NOT use:
- Headers with ## or ###
- Horizontal rules with --- or ***
- Bold/italic markers like **text** or *text*
- Bullet points with - or *
- Code blocks with ```
- Link formatting like [text](url)

Write naturally in plain text with proper paragraphs and line breaks. Be conversational and engaging."""

        # Generate response
        logger.info(f"Generating AI text response for message: {user_message[:50]}...")

        # Check if we have image attachments - use multimodal generation
        image_attachments = [att for att in (attachments or []) if (att.type if hasattr(att, 'type') else att.get("type", "")).startswith("image/")]

        if image_attachments:
            logger.info(f"Processing {len(image_attachments)} image attachment(s) with multimodal model")

            # Build multimodal content with text + images
            content_parts = [full_prompt]

            for img_att in image_attachments:
                try:
                    # Handle both dict and Pydantic model
                    img_data_b64 = img_att.data if hasattr(img_att, 'data') else img_att.get("data", "")
                    img_type = img_att.type if hasattr(img_att, 'type') else img_att.get("type", "image/png")
                    img_name = img_att.name if hasattr(img_att, 'name') else img_att.get('name', 'image')

                    # Decode base64 image data
                    img_data = base64.b64decode(img_data_b64)
                    # Add image part (Gemini will analyze the image with the text prompt)
                    content_parts.append({
                        "mime_type": img_type,
                        "data": img_data
                    })
                    logger.info(f"Added image: {img_name}")
                except Exception as e:
                    img_name = img_att.name if hasattr(img_att, 'name') else img_att.get('name', 'image')
                    logger.error(f"Failed to process image {img_name}: {str(e)}")

            response = model.generate_content(
                content_parts,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                }
            )
        else:
            # Standard text-only generation
            response = model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                }
            )

        ai_response = response.text
        logger.info("AI text response generated successfully")

        # Clean markdown formatting from response
        ai_response = clean_markdown_formatting(ai_response)
        logger.info("Cleaned markdown formatting from AI response")

        return (ai_response, None, "TEXT")

    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}", exc_info=True)
        return (
            f"I encountered an error while processing your request. Please try again. Error: {str(e)}",
            None,
            "TEXT"
        )


def chat_completion(
    project_id: int,
    user_message: str,
    include_history: bool = True,
    attachments: Optional[List[Dict]] = None
) -> Tuple[Dict, Dict]:
    """
    Complete chat interaction: save user message, generate AI response, save AI response.
    Returns tuple of (user_message_dict, ai_response_dict)
    """
    try:
        # Serialize attachments for database storage (without base64 data)
        import json
        attachments_json = None
        if attachments:
            attachments_json = json.dumps([{
                "name": att.name if hasattr(att, 'name') else att.get("name"),
                "type": att.type if hasattr(att, 'type') else att.get("type"),
                "size": att.size if hasattr(att, 'size') else att.get("size")
            } for att in attachments])

        # Save user message
        user_msg = save_chat_message(
            project_id=project_id,
            role="USER",
            content=user_message,
            content_type="MULTIMODAL" if attachments else "TEXT",
            attachments=attachments_json
        )
        # Ensure user_msg is a proper dict
        user_msg = dict(user_msg)

        # Get chat history if needed
        chat_history = None
        if include_history:
            chat_history, _ = get_chat_history(project_id)

        # Generate AI response (text and/or image)
        ai_response_text, image_url, content_type = generate_ai_response(user_message, chat_history, attachments)
        logger.info(f"Generated response - content_type: {content_type}, has_image_url: {image_url is not None}")

        # Save AI response with image if present
        # For IMAGE type, image_url is actually a data URL now (not a file path)
        if content_type == "IMAGE" and image_url:
            # Store data URL directly in database and return to frontend
            ai_msg = save_chat_message(
                project_id=project_id,
                role="ASSISTANT",
                content=image_url,  # Store data URL directly
                content_type=content_type,
                attachments=None
            )
            # Ensure ai_msg is a proper dict
            ai_msg = dict(ai_msg)
            logger.info(f"Saved generated image as data URL")
        else:
            ai_msg = save_chat_message(
                project_id=project_id,
                role="ASSISTANT",
                content=ai_response_text,
                content_type=content_type,
                attachments=None
            )
            # Ensure ai_msg is a proper dict
            ai_msg = dict(ai_msg)

        return user_msg, ai_msg

    except Exception as e:
        logger.error(f"Error in chat completion: {str(e)}", exc_info=True)
        raise
