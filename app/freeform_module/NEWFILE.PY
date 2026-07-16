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
import pdfplumber
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
        # generate + image/picture/photo/visual
        "generate image", "generate an image", "generate image of", "generate image for",
        "generate the image", "generate me an image", "generate me a image",
        "create image", "create an image", "create image of", "create image for",
        "create the image", "create me an image", "create me a image",
        "make image", "make an image", "make image of", "make image for",
        "make the image", "make me an image", "make me a image",
        "generate picture", "generate a picture", "generate picture of", "generate picture for",
        "generate the picture", "generate me a picture",
        "create picture", "create a picture", "create picture of", "create picture for",
        "create the picture", "create me a picture",
        "make picture", "make a picture", "make picture of", "make picture for",
        "make the picture", "make me a picture",
        "generate photo", "generate a photo", "generate photo of", "generate photo for",
        "generate the photo", "generate me a photo",
        "create photo", "create a photo", "create photo of", "create photo for",
        "create the photo", "create me a photo",
        "make photo", "make a photo", "make photo of", "make photo for",
        "make the photo", "make me a photo",
        # produce / render / craft / compose
        "produce an image", "produce a picture", "produce a photo",
        "produce image of", "produce picture of", "produce photo of",
        "render an image", "render a picture", "render a photo",
        "render image of", "render picture of", "render me",
        "craft an image", "craft a picture", "craft a photo",
        "compose an image", "compose a picture", "compose a visual",
        # show me
        "show me an image of", "show me a picture of", "show me a photo of",
        "show me an image", "show me a picture", "show me a photo",
        "show me a visual of", "show me what",
        "show image", "show picture", "show photo",
        # draw / sketch / paint
        "draw me", "draw an", "draw a", "draw this", "draw the",
        "sketch a", "sketch an", "sketch me", "sketch this", "sketch the",
        "paint me", "paint a", "paint an", "paint this", "paint the",
        # visualize / illustrate / depict / portray
        "visualize this", "visualize a", "visualize an", "visualize the",
        "illustration of", "illustrate a", "illustrate an", "illustrate this",
        "depict a", "depict an", "depict this", "depict the",
        "portray a", "portray an", "portray this", "portray the",
        # design / build / construct
        "generate visual", "create visual", "make visual",
        "design an image", "design a picture", "design a visual",
        "design me an image", "design me a picture", "design me a logo",
        "build an image", "build a picture", "build a visual",
        "construct an image", "construct a picture",
        # want / need / like
        "i want an image", "i want a picture", "i want a photo",
        "i want an image of", "i want a picture of", "i want a photo of",
        "i need an image", "i need a picture", "i need a photo",
        "i need an image of", "i need a picture of", "i need a photo of",
        "i'd like an image", "i'd like a picture", "i'd like a photo",
        "i would like an image", "i would like a picture", "i would like a photo",
        # can you / could you / please / would you
        "can you generate an image", "can you create an image", "can you make an image",
        "can you generate a picture", "can you create a picture", "can you make a picture",
        "can you draw", "can you paint", "can you sketch", "can you render",
        "could you generate an image", "could you create an image", "could you make an image",
        "could you draw", "could you paint", "could you sketch",
        "please generate an image", "please create an image", "please make an image",
        "please draw", "please paint", "please sketch",
        "would you generate an image", "would you create an image",
        # give me / get me / whip up / come up with (with and without articles)
        "give me image", "give me an image", "give me a picture", "give me a photo",
        "give me image of", "give me an image of", "give me a picture of", "give me a photo of",
        "give me picture", "give me picture of", "give me photo", "give me photo of",
        "get me image", "get me an image", "get me a picture", "get me a photo",
        "get me image of", "get me an image of", "get me a picture of", "get me a photo of",
        "get me picture", "get me picture of", "get me photo", "get me photo of",
        "whip up an image", "whip up a picture", "whip up image",
        "come up with an image", "come up with a picture", "come up with image",
        "put together an image", "put together a picture", "put together image",
        "mock up an image", "mock up a picture", "mock up image",
        # specific creative outputs
        "generate artwork", "create artwork", "make artwork",
        "generate a logo", "create a logo", "design a logo", "make a logo",
        "generate a banner", "create a banner", "design a banner", "make a banner",
        "generate a poster", "create a poster", "design a poster", "make a poster",
        "generate a wallpaper", "create a wallpaper", "design a wallpaper",
        "generate an icon", "create an icon", "design an icon",
        "generate a thumbnail", "create a thumbnail", "design a thumbnail",
        "generate a meme", "create a meme", "make a meme",
        "generate an infographic", "create an infographic", "design an infographic",
        "generate an avatar", "create an avatar", "design an avatar",
        "generate a diagram", "create a diagram", "design a diagram",
        "generate a flyer", "create a flyer", "design a flyer",
        "generate a background", "create a background", "design a background",
        "generate a cover", "create a cover", "design a cover",
        "generate a card", "create a card", "design a card",
        "generate a collage", "create a collage", "make a collage",
        "generate a sticker", "create a sticker", "design a sticker",
        "generate a cartoon", "create a cartoon", "draw a cartoon",
        "generate a sketch", "create a sketch",
        "generate a painting", "create a painting",
        "generate a portrait", "create a portrait", "paint a portrait",
        "generate a landscape", "create a landscape", "paint a landscape",
        # imagine / picture this
        "imagine a", "imagine an", "imagine this",
        "picture this", "picture a", "picture an",
    ]

    if any(phrase in message_lower for phrase in exact_phrases):
        return True

    # Check for flexible patterns like "generate [any words] image"
    action_words = [
        "generate", "create", "make", "produce", "design", "build",
        "render", "craft", "compose", "construct", "draw", "paint",
        "sketch", "illustrate", "depict", "whip up", "come up with",
    ]
    image_words = [
        "image", "picture", "photo", "visual", "illustration", "graphic",
        "artwork", "logo", "banner", "poster", "wallpaper", "icon",
        "thumbnail", "meme", "infographic", "avatar", "diagram",
        "flyer", "cover", "card", "collage", "sticker", "cartoon",
        "sketch", "painting", "portrait", "landscape", "drawing",
    ]

    # Pattern: action word followed by up to 3 words, then image word
    for action in action_words:
        for image_word in image_words:
            # Match patterns like "generate new image", "create a new picture", etc.
            pattern = rf"\b{re.escape(action)}\s+(?:\w+\s+){{0,3}}{re.escape(image_word)}\b"
            if re.search(pattern, message_lower):
                return True

    # Additional regex patterns for natural language variations
    flexible_patterns = [
        # "give me / get me [optional words] image/picture/photo" (catches with or without articles)
        r"\b(?:give|get)\s+me\s+(?:\w+\s+){0,3}(?:image|picture|photo|visual|artwork|logo|banner|poster|icon|thumbnail)\b",
        # "I want/need/would like ... image/picture/photo"
        r"\bi\s+(?:want|need|would\s+like|wanna|gotta\s+have)\s+(?:\w+\s+){0,4}(?:image|picture|photo|visual|artwork|logo|banner|poster)\b",
        # "can/could/would you ... image/picture/photo"
        r"\b(?:can|could|would|will)\s+you\s+(?:\w+\s+){0,4}(?:image|picture|photo|visual|artwork|logo|banner)\b",
        # "please ... image/picture/photo"
        r"\bplease\s+(?:\w+\s+){0,4}(?:image|picture|photo|visual|artwork|logo|banner)\b",
        # "show me what ... looks like"
        r"\bshow\s+me\s+(?:what|how)\s+.{1,50}\s+looks?\s+like\b",
        # "turn this into an image/picture"
        r"\bturn\s+(?:this|that|it)\s+into\s+(?:an?\s+)?(?:image|picture|photo|visual)\b",
        # "convert this to an image/picture"
        r"\bconvert\s+(?:this|that|it)\s+(?:to|into)\s+(?:an?\s+)?(?:image|picture|photo|visual)\b",
    ]

    for pattern in flexible_patterns:
        if re.search(pattern, message_lower):
            return True

    return False


def detect_image_edit_request(message: str) -> bool:
    """Detect if user wants to edit/modify an attached image (not just analyze it)."""
    message_lower = message.lower().strip()

    # Phrases that indicate the user wants a MODIFIED image back
    edit_phrases = [
        # refine / edit / modify
        "refine this image", "refine the image", "refine image", "refine it",
        "refine this picture", "refine the picture", "refine this photo",
        "edit this image", "edit the image", "edit image",
        "edit this picture", "edit the picture", "edit this photo",
        "modify this image", "modify the image", "modify image",
        "modify this picture", "modify the picture", "modify this photo",
        # background changes
        "change background", "change the background", "change its background",
        "remove background", "remove the background", "remove its background",
        "replace the background", "replace background", "swap the background", "swap background",
        "make the background", "set the background", "set background to",
        "transparent background", "make background transparent",
        "white background", "black background", "blur the background", "blur background",
        # color changes
        "change color", "change the color", "change colors", "change the colors",
        "change colour", "change the colour", "change colours", "change the colours",
        "recolor", "recolour", "change the hue", "shift the color",
        "make it more colorful", "make it more colourful",
        "make it less colorful", "make it less colourful",
        "desaturate", "saturate", "add saturation", "remove saturation",
        "invert colors", "invert the colors", "invert colours",
        # brightness / contrast / exposure
        "make it brighter", "make it darker", "make it sharper",
        "make it lighter", "make it more", "make it less",
        "make it warmer", "make it cooler", "make it softer",
        "make it clearer", "make it crisper", "make it vivid",
        "make this image", "make the image",
        "increase contrast", "decrease contrast", "more contrast", "less contrast",
        "increase brightness", "decrease brightness", "more brightness", "less brightness",
        "increase saturation", "decrease saturation",
        "increase sharpness", "decrease sharpness",
        "adjust exposure", "fix exposure", "correct exposure",
        "adjust brightness", "adjust contrast", "adjust saturation",
        # enhance / improve / fix
        "enhance this image", "enhance the image", "enhance image", "enhance it",
        "enhance this picture", "enhance the picture", "enhance this photo",
        "enhance quality", "enhance the quality", "enhance resolution",
        "improve this image", "improve the image", "improve image", "improve it",
        "improve this picture", "improve the picture", "improve this photo",
        "improve quality", "improve the quality", "improve resolution",
        "fix this image", "fix the image", "fix this picture", "fix this photo",
        "fix the lighting", "fix the colors", "fix the quality",
        "clean up this image", "clean up the image", "clean this up",
        "restore this image", "restore the image", "restore this photo",
        "upscale this image", "upscale the image", "upscale this",
        "sharpen this", "brighten this", "darken this",
        # filters and effects
        "add filter", "apply filter", "add a filter", "apply a filter",
        "add effect", "apply effect", "add an effect", "apply an effect",
        "make it black and white", "make it grayscale", "make it greyscale",
        "make it sepia", "apply sepia", "sepia tone",
        "make it vintage", "make it retro", "vintage effect", "retro effect",
        "add glow", "add shadow", "add shadows", "add highlights",
        "add vignette", "apply vignette",
        "add noise", "remove noise", "reduce noise",
        "add grain", "remove grain",
        # crop / resize / rotate / flip
        "crop this", "crop the image", "crop this image", "crop it",
        "resize this", "resize the image", "resize this image", "resize it",
        "rotate this", "rotate the image", "rotate this image", "rotate it",
        "flip this", "flip the image", "flip this image", "flip it",
        "mirror this", "mirror the image", "mirror this image",
        "scale this", "scale the image", "scale it up", "scale it down",
        "zoom in", "zoom out", "zoom into",
        "make it square", "make it wider", "make it taller",
        "change the aspect ratio", "change aspect ratio",
        "make it bigger", "make it smaller", "make it larger",
        # add / remove elements
        "add text to", "add watermark", "add a watermark",
        "remove text from", "remove watermark", "remove the watermark",
        "add a border", "add border", "add a frame", "add frame",
        "remove the border", "remove border", "remove the frame",
        "add a logo", "add logo", "overlay text", "overlay a text",
        "remove object", "remove the object", "remove person", "remove the person",
        "remove element", "remove this", "erase this", "erase the",
        "add something", "put something", "place something",
        "add an overlay", "add overlay",
        # convert / transform / adjust
        "convert this image", "convert the image", "convert it to",
        "transform this image", "transform the image", "transform this",
        "adjust this image", "adjust the image", "adjust this",
        "update this image", "update the image",
        "change this image", "change the image",
        # style changes
        "change style", "change the style", "change its style",
        "make it look like", "make it look more", "make it look less",
        "apply style", "apply a style", "style transfer",
        "make it artistic", "make it realistic", "make it abstract",
        "make it minimalist", "make it detailed",
        "change the mood", "change mood",
        "change the tone", "change tone",
        "change the lighting", "change lighting", "fix lighting", "adjust lighting",
        # redo / regenerate / tweak
        "regenerate this", "redo this image", "redo this",
        "tweak this", "tweak the image", "tweak it",
        "touch up", "retouch", "retouch this",
        "revise this image", "revise the image",
        "alter this image", "alter the image",
        # colorize / paint over / extend
        "colorize this", "colorize the image", "colorize it",
        "paint over", "paint on", "draw on",
        "extend this image", "extend the image", "extend it",
        "expand this image", "expand the image",
        "fill in", "inpaint", "outpaint",
        # can you / could you / please variants
        "can you edit", "can you modify", "can you change", "can you fix",
        "can you enhance", "can you improve", "can you adjust",
        "could you edit", "could you modify", "could you change",
        "please edit", "please modify", "please change", "please fix",
        "please enhance", "please improve",
    ]

    if any(phrase in message_lower for phrase in edit_phrases):
        return True

    # Pattern: action word + "the/this/my/that" + image-related word
    import re
    edit_actions = [
        "refine", "edit", "modify", "change", "enhance", "improve",
        "fix", "adjust", "transform", "update", "crop", "resize",
        "sharpen", "brighten", "darken", "blur", "rotate", "flip",
        "mirror", "scale", "restore", "upscale", "clean", "retouch",
        "tweak", "revise", "alter", "colorize", "extend", "expand",
    ]
    for action in edit_actions:
        pattern = rf"\b{action}\s+(?:the\s+|this\s+|my\s+|that\s+|its\s+)?(?:image|picture|photo|pic|photograph|img)\b"
        if re.search(pattern, message_lower):
            return True

    return False


def detect_content_with_image_request(message: str) -> bool:
    """Detect if user wants both text content AND image generation in the same request.
    Returns True ONLY when user very explicitly asks for text content alongside the image.
    Must be strict to avoid false positives - when in doubt, return False (image only).

    Examples that return True:
      - "generate image of a cat and also write about cats"
      - "create a picture of sunset and also explain about sunsets"
      - "generate both image and text about dogs"
    Examples that return False (image only):
      - "generate image of a cat"
      - "create a picture with a description"
      - "draw me a sunset"
    """
    import re
    message_lower = message.lower().strip()

    # Only match very explicit requests for BOTH text and image
    # Note: use (?:an?\s+|the\s+|some\s+)? to handle "a", "an", "the", "some" articles
    text_words = r"(?:text|content|article|blog|post|story|poem|paragraph|explanation|caption|description|summary|write-up|writeup|essay|report|information|details|info)"
    image_words_pattern = r"(?:image|picture|photo|visual|illustration|artwork|graphic)"

    combined_patterns = [
        # "and also write/explain/tell/give/provide about..."
        r"\band\s+also\s+(?:write|explain|tell|give|provide|describe|elaborate)\b",
        # "also write/explain/generate text/content..."
        rf"\balso\s+(?:write|explain|generate|create|give|provide)\s+(?:me\s+)?(?:an?\s+|some\s+|the\s+)?{text_words}\b",
        # "generate/create both image and text/content"
        rf"\bboth\s+{image_words_pattern}\s+and\s+(?:an?\s+|the\s+|some\s+)?{text_words}\b",
        rf"\bboth\s+{text_words}\s+and\s+(?:an?\s+|the\s+|some\s+)?{image_words_pattern}\b",
        # "along with a/an/the/some text/article/blog/content/explanation"
        rf"\balong\s+with\s+(?:an?\s+|the\s+|some\s+)?{text_words}\b",
        # "generate image and text" / "generate image and content" (explicit text/content word)
        rf"\b(?:generate|create|make|produce)\s+(?:an?\s+)?{image_words_pattern}\s+and\s+(?:an?\s+|the\s+|some\s+)?{text_words}\b",
        rf"\b(?:generate|create|make|produce)\s+(?:an?\s+)?{text_words}\s+and\s+(?:an?\s+)?{image_words_pattern}\b",
        # "with a description/explanation/caption"
        rf"\bwith\s+(?:an?\s+|the\s+|some\s+)?{text_words}\b",
        # "and describe/explain it"
        r"\band\s+(?:describe|explain|write\s+about|tell\s+me\s+about)\b",
        # "write about it too / as well / also"
        r"\b(?:write|explain|describe)\s+(?:about\s+)?(?:it|this|that)\s+(?:too|also|as\s+well)\b",
        # "include text/description/explanation"
        rf"\binclude\s+(?:an?\s+|the\s+|some\s+)?{text_words}\b",
        # "add text/description alongside"
        rf"\badd\s+(?:an?\s+|the\s+|some\s+)?{text_words}\s+(?:alongside|with\s+it|too|also)\b",
        # "I also want/need text/description"
        rf"\bi\s+also\s+(?:want|need|would\s+like)\s+(?:an?\s+|the\s+|some\s+)?{text_words}\b",
        # "plus a description/explanation"
        rf"\bplus\s+(?:an?\s+|the\s+|some\s+)?{text_words}\b",
        # "and a/an/the/some description/explanation" (with required article)
        rf"\band\s+(?:an?\s+|the\s+|some\s+){text_words}\b",
        # "and [optional words like '5 line'] content/text/description about/on/for" (handles "and 5 line content about mountain")
        rf"\band\s+(?:\w+\s+){{0,3}}{text_words}\s+(?:about|on|for|regarding|of)\b",
        # "and [number] lines/points/paragraphs about/on" (handles "and 5 lines about", "and 3 points on")
        r"\band\s+\d+\s+(?:lines?|points?|paragraphs?|sentences?|words?)\s+(?:about|on|for|regarding|of)\b",
        # "and write/give/provide [number] lines/points about"
        r"\band\s+(?:write|give|provide|generate|create)\s+(?:me\s+)?\d+\s+(?:lines?|points?|paragraphs?|sentences?)\s+(?:about|on|for|regarding|of)\b",
        # "[number] line/lines content/text about" anywhere in message
        rf"\b\d+\s+(?:lines?\s+|sentences?\s+|paragraphs?\s+|points?\s+)?{text_words}\s+(?:about|on|for|regarding|of)\b",
    ]

    for pattern in combined_patterns:
        if re.search(pattern, message_lower):
            return True

    return False


def find_last_generated_image(chat_history: Optional[List[Dict]]) -> Optional[str]:
    """Find the most recent AI-generated image from chat history.
    Returns the base64 data URL string if found, None otherwise.
    Searches in reverse order (most recent first).
    """
    if not chat_history:
        return None

    for msg in reversed(chat_history):
        role = msg.get("role", "USER")
        if role != "ASSISTANT":
            continue

        content_type = msg.get("content_type", "TEXT")
        if hasattr(content_type, 'value'):
            content_type = content_type.value
        content = msg.get("content", "")
        attachments = msg.get("attachments", "")

        # IMAGE type: data URL stored in content field
        if content_type == "IMAGE" and content and str(content).startswith("data:image/"):
            logger.info("Found last generated image in content field (IMAGE type)")
            return content

        # MULTIMODAL type: image data URL stored in attachments field
        if content_type == "MULTIMODAL" and attachments and str(attachments).startswith("data:image/"):
            logger.info("Found last generated image in attachments field (MULTIMODAL type)")
            return attachments

    return None


def edit_image(prompt: str, image_data: bytes, mime_type: str) -> Optional[str]:
    """Edit an image using Gemini Image API with the uploaded image + instruction. Returns data URL."""
    logger.info("=== edit_image() called ===")
    logger.info(f"Image client available: {image_client is not None}")
    logger.info(f"IMAGE_MODEL_ID: {IMAGE_MODEL_ID}")

    if not image_client or not IMAGE_MODEL_ID:
        logger.error("Image editing requested but image client not configured")
        return None

    try:
        logger.info(f"Edit image prompt: {prompt[:200]}...")

        # Send both the instruction text and the uploaded image to the image model
        parts = [
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=image_data, mime_type=mime_type)
        ]
        resp = image_client.models.generate_content(
            model=IMAGE_MODEL_ID,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
        )

        logger.info(f"API response received: {resp is not None}")

        if not resp or not getattr(resp, "candidates", None):
            logger.warning("Image editing: No candidates in response")
            return None

        # Extract image data from response
        for i, part in enumerate(resp.candidates[0].content.parts):
            if hasattr(part, "inline_data") and part.inline_data:
                result_mime = getattr(part.inline_data, 'mime_type', 'image/png')
                image_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                data_url = f"data:{result_mime};base64,{image_b64}"
                logger.info(f"Image edited successfully via inline_data (mime: {result_mime})")
                return data_url
            if hasattr(part, "image") and part.image:
                image_b64 = base64.b64encode(part.image.image_bytes).decode("utf-8")
                data_url = f"data:image/png;base64,{image_b64}"
                logger.info(f"Image edited successfully via image.image_bytes")
                return data_url

        logger.warning("Image editing: No image data found in response parts")
        return None

    except Exception as e:
        logger.error(f"Error editing image: {str(e)}", exc_info=True)
        return None


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
            # generate + image/picture/photo
            "generate image of ", "generate an image of ", "generate image for ",
            "generate me an image of ", "generate the image of ",
            "generate a picture of ", "generate picture of ",
            "generate a photo of ", "generate photo of ",
            # create + image/picture/photo
            "create image of ", "create an image of ", "create image for ",
            "create me an image of ", "create the image of ",
            "create a picture of ", "create picture of ",
            "create a photo of ", "create photo of ",
            # make + image/picture/photo
            "make image of ", "make an image of ", "make image for ",
            "make me an image of ", "make the image of ",
            "make a picture of ", "make picture of ",
            "make a photo of ", "make photo of ",
            # produce / render / craft / compose
            "produce an image of ", "produce a picture of ", "produce a photo of ",
            "render an image of ", "render a picture of ", "render a photo of ",
            "render me ", "craft an image of ", "craft a picture of ",
            "compose an image of ", "compose a picture of ",
            # draw / sketch / paint
            "draw me a ", "draw me an ", "draw me ",
            "draw an ", "draw a ", "draw ",
            "sketch me a ", "sketch me an ", "sketch a ", "sketch an ", "sketch ",
            "paint me a ", "paint me an ", "paint a ", "paint an ", "paint ",
            # show me
            "show me an image of ", "show me a picture of ", "show me a photo of ",
            "show me a visual of ", "show me what ",
            # design / build / construct
            "design an image of ", "design a picture of ", "design a visual of ",
            "design me an image of ", "design me a ",
            "build an image of ", "build a picture of ",
            "construct an image of ",
            # illustrate / depict / portray / visualize
            "illustrate a ", "illustrate an ", "illustrate ",
            "depict a ", "depict an ", "depict ",
            "portray a ", "portray an ", "portray ",
            "visualize a ", "visualize an ", "visualize this ",
            # give me / get me / whip up (with and without articles)
            "give me image of ", "give me an image of ", "give me a picture of ", "give me a photo of ",
            "give me picture of ", "give me photo of ",
            "get me image of ", "get me an image of ", "get me a picture of ", "get me a photo of ",
            "get me picture of ", "get me photo of ",
            "whip up an image of ", "whip up a picture of ",
            "come up with an image of ", "come up with a picture of ",
            "put together an image of ", "put together a picture of ",
            "mock up an image of ", "mock up a picture of ",
            # want / need / like
            "i want an image of ", "i want a picture of ", "i want a photo of ",
            "i need an image of ", "i need a picture of ", "i need a photo of ",
            "i'd like an image of ", "i'd like a picture of ", "i'd like a photo of ",
            "i would like an image of ", "i would like a picture of ",
            # can you / could you / please
            "can you generate an image of ", "can you create an image of ", "can you make an image of ",
            "can you draw ", "can you paint ", "can you sketch ",
            "could you generate an image of ", "could you create an image of ",
            "could you draw ", "could you paint ", "could you sketch ",
            "please generate an image of ", "please create an image of ",
            "please draw ", "please paint ", "please sketch ",
            # specific creative outputs
            "generate a logo of ", "create a logo of ", "design a logo of ", "design a logo for ",
            "generate a banner of ", "create a banner of ", "design a banner for ",
            "generate a poster of ", "create a poster of ", "design a poster for ",
            "generate artwork of ", "create artwork of ",
            # imagine / picture this
            "imagine a ", "imagine an ", "imagine ",
            "picture this ", "picture a ", "picture an ",
            # fallback short forms
            "generate it", "create it", "make it",
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

        candidate = resp.candidates[0]
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) if content else None

        if not parts:
            # Log finish_reason if available to help diagnose why no parts were returned
            finish_reason = getattr(candidate, "finish_reason", None)
            logger.warning(f"Image generation: No content parts in candidate (finish_reason={finish_reason})")
            return None

        # Extract image data
        for i, part in enumerate(parts):
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
            updated = dict(updated_projects[0]._mapping)
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
    """Extract text content from a PDF file. Tries PyPDF2 first, falls back to pdfplumber."""
    # Try PyPDF2 first
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(decoded_data))
        pages_text = []
        for i, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text and page_text.strip():
                pages_text.append(f"[Page {i + 1}]\n{page_text.strip()}")
        if pages_text:
            return f"--- File: {file_name} (PDF - {len(pdf_reader.pages)} pages) ---\n" + "\n\n".join(pages_text) + "\n"
    except Exception as e:
        logger.warning(f"PyPDF2 failed for {file_name}: {str(e)}, trying pdfplumber...")

    # Fallback to pdfplumber (handles more PDF formats)
    try:
        pdf = pdfplumber.open(io.BytesIO(decoded_data))
        pages_text = []
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text and page_text.strip():
                pages_text.append(f"[Page {i + 1}]\n{page_text.strip()}")

            # Also extract tables if present
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):
                if table:
                    table_rows = []
                    for row in table:
                        row_data = [str(cell).strip() if cell else "" for cell in row]
                        table_rows.append("\t".join(row_data))
                    if table_rows:
                        pages_text.append(f"[Page {i + 1} - Table {t_idx + 1}]\n" + "\n".join(table_rows))
        pdf.close()

        if pages_text:
            return f"--- File: {file_name} (PDF - {len(pdf.pages)} pages) ---\n" + "\n\n".join(pages_text) + "\n"
        else:
            return f"[PDF file attached: {file_name} - Could not extract text (may be scanned/image-based)]"
    except Exception as e2:
        logger.error(f"Both PyPDF2 and pdfplumber failed for {file_name}: {str(e2)}")
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

    # Remove JSON/action blocks that the model sometimes outputs (e.g. {"action": "dalle.text2im", ...})
    # Uses brace-depth tracking to handle nested braces inside the JSON
    cleaned = text
    i = 0
    while i < len(cleaned):
        if cleaned[i] == '{':
            # Track brace depth to find matching closing brace
            depth = 1
            j = i + 1
            while j < len(cleaned) and depth > 0:
                if cleaned[j] == '{':
                    depth += 1
                elif cleaned[j] == '}':
                    depth -= 1
                j += 1
            if depth == 0:
                block = cleaned[i:j]
                if '"action"' in block or '"thought"' in block or '"action_input"' in block:
                    # Remove the JSON block and any trailing whitespace
                    cleaned = cleaned[:i] + cleaned[j:].lstrip()
                    continue  # Re-check from same position
        i += 1
    text = cleaned

    # Remove markdown headers (## Header, ### Header, etc.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove horizontal rules (---, ***, ___)
    text = re.sub(r'^[\-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Remove bold/italic markers (**text**, __text__, *text*, _text_)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # Keep bullet points and numbered lists - the frontend renders them as HTML lists

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
        # Check if user has attached files
        has_attachments = attachments and len(attachments) > 0
        has_image_attachments = has_attachments and any(
            (att.type if hasattr(att, 'type') else att.get("type", "")).startswith("image/")
            for att in attachments
        )
        logger.info(f"Has attachments: {has_attachments}, Has image attachments: {has_image_attachments}")

        # Check if user is requesting image generation
        # BUT if user has attached images, they want to ANALYZE the image, not generate a new one
        is_image_request = detect_image_request(user_message) and not has_image_attachments
        logger.info(f"Message: '{user_message[:100]}...' | Image generation request: {is_image_request}")

        # Build context from chat history (filter out base64 image data to avoid token overflow)
        context_str = ""
        if chat_history:
            recent_history = chat_history[-5:] if len(chat_history) > 5 else chat_history
            context_parts = []
            for msg in recent_history:
                role = msg.get("role", "USER")
                content = msg.get("content", "")
                content_type = msg.get("content_type", "TEXT")
                if hasattr(content_type, 'value'):
                    content_type = content_type.value
                # Skip base64 image content - replace with placeholder
                if content_type == "IMAGE" or (content and content.startswith("data:image/")):
                    content = "[Generated image]"
                elif content and len(content) > 50000:
                    content = content[:50000] + "... [truncated]"
                if role == "USER":
                    context_parts.append(f"User: {content}")
                elif role == "ASSISTANT":
                    context_parts.append(f"Assistant: {content}")
            context_str = "\n".join(context_parts)

        # If image generation requested (no image attachments), generate image
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
                logger.info("Image generated successfully")
                # Check if user also wants text content alongside the image
                wants_text_too = detect_content_with_image_request(user_message)
                logger.info(f"User wants text alongside image: {wants_text_too}")

                if wants_text_too:
                    # User asked for both text and image - generate text response too
                    try:
                        if GEMINI_API_KEY:
                            text_model = genai.GenerativeModel(FREEFORM_MODEL_ID)
                            text_parts = []
                            if context_str:
                                text_parts.append(context_str)
                            text_parts.append(f"User: {user_message}")
                            text_parts.append(
                                "\nIMPORTANT INSTRUCTIONS: An image has already been generated separately. "
                                "Your job is ONLY to provide a clean, plain text informational response about the topic. "
                                "Do NOT output any JSON, action objects, structured data, tool calls, or code blocks. "
                                "Do NOT include anything like {\"action\": ...} or {\"thought\": ...} or dalle prompts. "
                                "Do NOT mention generating images or that you cannot create images. "
                                "Just write natural, conversational plain text about the topic."
                            )
                            text_prompt = "\n\n".join(text_parts)
                            text_response = text_model.generate_content(
                                text_prompt,
                                generation_config={
                                    "temperature": 0.7,
                                    "top_p": 0.95,
                                    "top_k": 40,
                                    "max_output_tokens": 8192,
                                }
                            )
                            cleaned_text = clean_markdown_formatting(text_response.text)
                            if cleaned_text and cleaned_text.strip():
                                logger.info("Combined text+image response generated")
                                return (cleaned_text, image_b64, "MULTIMODAL")
                    except Exception as e:
                        logger.error(f"Error generating text for combined response: {e}")

                # Image only - user only asked for an image
                logger.info("Returning image-only response")
                return ("", image_b64, "IMAGE")
            else:
                logger.error("Image generation returned None")
                return (
                    "I'm sorry, I encountered an error while generating the image. Please try again.",
                    None,
                    "TEXT"
                )

        # If user uploaded an image and wants to edit/modify it, use image model
        if has_image_attachments and detect_image_edit_request(user_message):
            logger.info("=== IMAGE EDITING PATH ===")

            if not image_client:
                logger.error("Image client is not initialized for editing")
                return (
                    "Image editing is not configured. Please contact administrator.",
                    None,
                    "TEXT"
                )

            # Get the first image attachment
            img_att = None
            for att in attachments:
                att_type = att.type if hasattr(att, 'type') else att.get("type", "")
                if att_type.startswith("image/"):
                    img_att = att
                    break

            if img_att:
                try:
                    img_data_b64 = img_att.data if hasattr(img_att, 'data') else img_att.get("data", "")
                    img_type = img_att.type if hasattr(img_att, 'type') else img_att.get("type", "image/png")
                    img_name = img_att.name if hasattr(img_att, 'name') else img_att.get('name', 'image')

                    img_data = base64.b64decode(img_data_b64)
                    logger.info(f"Editing image: {img_name} ({img_type}), instruction: {user_message[:100]}...")

                    edited_image = edit_image(user_message, img_data, img_type)

                    if edited_image:
                        logger.info("Image edited successfully, returning to user")
                        return (
                            "",  # Empty text - just show the edited image
                            edited_image,
                            "IMAGE"
                        )
                    else:
                        logger.error("Image editing returned None")
                        return (
                            "I'm sorry, I couldn't edit the image. Please try again with a different instruction.",
                            None,
                            "TEXT"
                        )
                except Exception as e:
                    logger.error(f"Error in image editing flow: {str(e)}", exc_info=True)
                    return (
                        f"I encountered an error while editing the image. Please try again.",
                        None,
                        "TEXT"
                    )

        # If user wants to edit a previously generated image (no attachment, but edit request + image in history)
        if not has_image_attachments and detect_image_edit_request(user_message):
            logger.info("=== IMAGE EDIT FROM HISTORY PATH ===")
            last_image_data_url = find_last_generated_image(chat_history)

            if last_image_data_url:
                if not image_client:
                    logger.error("Image client is not initialized for editing from history")
                    return (
                        "Image editing is not configured. Please contact administrator.",
                        None,
                        "TEXT"
                    )

                try:
                    # Extract base64 data and mime type from data URL
                    # Format: data:image/png;base64,<base64_data>
                    header, b64_data = last_image_data_url.split(",", 1)
                    img_type = header.split(":")[1].split(";")[0]  # e.g. "image/png"

                    img_data = base64.b64decode(b64_data)
                    logger.info(f"Editing previous image from history ({img_type}), instruction: {user_message[:100]}...")

                    edited_image = edit_image(user_message, img_data, img_type)

                    if edited_image:
                        logger.info("Image from history edited successfully")
                        # Check if user also wants text with the edit
                        wants_text_too = detect_content_with_image_request(user_message)
                        if wants_text_too:
                            try:
                                if GEMINI_API_KEY:
                                    text_model = genai.GenerativeModel(FREEFORM_MODEL_ID)
                                    text_parts = []
                                    if context_str:
                                        text_parts.append(context_str)
                                    text_parts.append(f"User: {user_message}")
                                    text_parts.append(
                                        "\nIMPORTANT INSTRUCTIONS: An image has been edited and is shown separately. "
                                        "Your job is ONLY to provide a clean, plain text response about the changes made. "
                                        "Do NOT output any JSON, action objects, structured data, or tool calls. "
                                        "Just write natural, conversational plain text."
                                    )
                                    text_prompt = "\n\n".join(text_parts)
                                    text_response = text_model.generate_content(
                                        text_prompt,
                                        generation_config={
                                            "temperature": 0.7,
                                            "top_p": 0.95,
                                            "top_k": 40,
                                            "max_output_tokens": 8192,
                                        }
                                    )
                                    cleaned_text = clean_markdown_formatting(text_response.text)
                                    if cleaned_text and cleaned_text.strip():
                                        return (cleaned_text, edited_image, "MULTIMODAL")
                            except Exception as e:
                                logger.error(f"Error generating text for edited image: {e}")

                        return ("", edited_image, "IMAGE")
                    else:
                        logger.error("Image editing from history returned None")
                        return (
                            "I'm sorry, I couldn't edit the image. Please try again with a different instruction.",
                            None,
                            "TEXT"
                        )
                except Exception as e:
                    logger.error(f"Error in image editing from history: {str(e)}", exc_info=True)
                    return (
                        "I encountered an error while editing the image. Please try again.",
                        None,
                        "TEXT"
                    )
            else:
                logger.info("User requested image edit but no previous image found in history")

        # Otherwise, generate text response
        if not GEMINI_API_KEY:
            return (
                "AI service is not configured. Please contact administrator.",
                None,
                "TEXT"
            )

        # Initialize the model
        model = genai.GenerativeModel(FREEFORM_MODEL_ID)

        # Build conversation history for context (filter out base64 image data to avoid token overflow)
        conversation_parts = []
        total_history_chars = 0
        MAX_HISTORY_CHARS = 500000  # ~125K tokens safety limit for history

        if chat_history:
            # Add previous messages for context (limit to last 10 messages to avoid token limits)
            recent_history = chat_history[-10:] if len(chat_history) > 10 else chat_history

            for msg in recent_history:
                role = msg.get("role", "USER")
                content = msg.get("content", "")
                content_type = msg.get("content_type", "TEXT")
                if hasattr(content_type, 'value'):
                    content_type = content_type.value

                # Skip base64 image content - replace with placeholder
                if content_type == "IMAGE" or (content and content.startswith("data:image/")):
                    content = "[Generated image]"
                elif content and len(content) > 50000:
                    content = content[:50000] + "... [truncated]"

                # Check total history size to prevent token overflow
                if total_history_chars + len(content) > MAX_HISTORY_CHARS:
                    logger.warning(f"Chat history truncated at {total_history_chars} chars to avoid token overflow")
                    break

                total_history_chars += len(content)

                if role == "USER":
                    conversation_parts.append(f"User: {content}")
                elif role == "ASSISTANT":
                    conversation_parts.append(f"Assistant: {content}")

        # Process attachments to add context
        attachment_context = ""
        if attachments:
            attachment_context = process_text_attachments(attachments)
            if attachment_context:
                conversation_parts.append(f"[ATTACHED DOCUMENT CONTENT - Read this carefully and use it to answer the user's question]:\n{attachment_context}")

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
- Document analysis (PDF, Word, Excel, CSV, text files)
- Image analysis and description

IMPORTANT RULES FOR ATTACHED DOCUMENTS:
- When document content is provided in the conversation, you MUST read and analyze it thoroughly before responding.
- Base your response ENTIRELY on the actual document content provided. Do not make up information.
- When asked to summarize, explain, or answer questions about a document, give precise, detailed answers drawn directly from the document text.
- Include specific details, numbers, names, and facts from the document.
- If the document content is truncated, mention that you only have partial content.

IMPORTANT RULES FOR ATTACHED IMAGES:
- When images are attached, analyze them carefully and respond based on what you see.
- Provide detailed and accurate descriptions when asked about an image.
- If asked to extract text from an image, do your best to read and transcribe visible text.

FORMATTING RULES:
- When the user asks for bullet points, numbered lists, or step-by-step format, USE them with markdown syntax (- for bullets, 1. 2. 3. for numbered lists).
- You may use **bold** for emphasis when appropriate.
- Do NOT use headers with ## or ###.
- Do NOT use horizontal rules with --- or ***.
- Do NOT use code blocks with ```.
- Do NOT use link formatting like [text](url).
- Do NOT output JSON objects, structured data like {"action": ...} or {"thought": ...}, or any tool call format.

NEVER output JSON, action objects, structured data, or tool calls in your response.
Do not include any "thought" or "action" or "action_input" fields.

Write naturally with proper paragraphs, line breaks, and use bullet/numbered lists when the user requests them. Be conversational and engaging."""

        # Safety check: truncate full_prompt if it's too large (~750K chars ≈ ~187K tokens)
        MAX_PROMPT_CHARS = 750000
        if len(full_prompt) > MAX_PROMPT_CHARS:
            logger.warning(f"Full prompt too large ({len(full_prompt)} chars), truncating to {MAX_PROMPT_CHARS}")
            full_prompt = full_prompt[:MAX_PROMPT_CHARS] + "\n\n[Earlier conversation history truncated to fit within limits]"

        # Generate response
        logger.info(f"Generating AI text response for message: {user_message[:50]}... (prompt size: {len(full_prompt)} chars)")

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
                    "max_output_tokens": 8192,
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
                    "max_output_tokens": 8192,
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
        if content_type == "MULTIMODAL" and image_url:
            # Both text and image - text in content, image data URL in attachments
            ai_msg = save_chat_message(
                project_id=project_id,
                role="ASSISTANT",
                content=ai_response_text,
                content_type=content_type,
                attachments=image_url
            )
            ai_msg = dict(ai_msg)
            logger.info("Saved combined text+image response")
        elif content_type == "IMAGE" and image_url:
            # Image only - store data URL directly in content
            ai_msg = save_chat_message(
                project_id=project_id,
                role="ASSISTANT",
                content=image_url,
                content_type=content_type,
                attachments=None
            )
            ai_msg = dict(ai_msg)
            logger.info("Saved generated image as data URL")
        else:
            # Text only
            ai_msg = save_chat_message(
                project_id=project_id,
                role="ASSISTANT",
                content=ai_response_text,
                content_type=content_type,
                attachments=None
            )
            ai_msg = dict(ai_msg)

        return user_msg, ai_msg

    except Exception as e:
        logger.error(f"Error in chat completion: {str(e)}", exc_info=True)
        raise
