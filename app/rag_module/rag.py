# rag_engine.py
import os
import base64
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from dotenv import load_dotenv
from service_utils.db_utils.weaviate_db import WeaviateDB
from weaviate_module.weaviate_utils import load_data_with_tracking

import google.generativeai as genai
from google import genai as genai_new
from google.genai import types

from rag_module.telemetry import Telemetry
from rag_module.understanding_prompts import build_full_understanding_prompt
from rag_module.case_study_prompts import build_project_case_study_prompt
from rag_module.resource_prompts import build_resource_prompt
from rag_module.policy_prompts import build_policy_prompt
from rag_module.newsletter_prompts import build_quarterly_newsletter_prompt
from rag_module.image_prompts import build_image_prompt, detect_visual_mode
from rag_module.max_line_detector import detect_max_lines_from_query

load_dotenv()

# ---------------- CONFIG ----------------
TEXT_MODEL_TIMEOUT_SEC = 60  # Increased from 20 to 60 seconds
IMAGE_MODEL_TIMEOUT_SEC = 90  # Increased from 30 to 90 seconds

MAX_CONTEXT_CHUNKS = 6
MAX_CHARS_PER_CHUNK = 1200
CACHE_SIZE = 128

UNREACHABLE_TEXT = (
    "We're having trouble reaching the AI agent right now. "
    "Your request wasn't lost. Please try again in a moment."
)

NETWORK_ERROR_TEXT = (
    "Unable to connect to the AI service due to network issues. "
    "Please check your internet connection and try again."
)

OUT_OF_SCOPE_TEXT = (
    "This question is outside the scope of the provided context."
)


class RagModule:

    # ---------------- INIT ----------------
    def __init__(self):
        self.client = WeaviateDB().client
        self.collection = self.client.collections.get("training_data")

        self.executor = ThreadPoolExecutor(max_workers=4)

        # Configure text model
        text_api_key = os.getenv("GEMINI_TEXT_API_KEY")
        if not text_api_key:
            print("WARNING: GEMINI_TEXT_API_KEY not set in environment")
        genai.configure(api_key=text_api_key)
        
        text_model_id = os.getenv("TEXT_MODEL_ID", "gemini-3-flash-preview")
        print(f"Initializing text model: {text_model_id}")
        self.text_model = genai.GenerativeModel(text_model_id)

        # Configure image model
        image_api_key = os.getenv("GEMINI_IMAGE_API_KEY")
        image_model_id = os.getenv("IMAGE_MODEL_ID")
        
        if not image_api_key:
            print("WARNING: GEMINI_IMAGE_API_KEY not set in environment")
        if not image_model_id:
            print("WARNING: IMAGE_MODEL_ID not set in environment")
        
        print(f"Initializing image model: {image_model_id}")
        self.image_client = genai_new.Client(
            api_key=image_api_key,
            http_options={"api_version": "v1beta"}
        )

    # ---------------- CONTEXT ----------------
    @lru_cache(maxsize=CACHE_SIZE)
    def retrieve_context(self, query: str):
        res = self.collection.query.bm25(
            query=query,
            limit=MAX_CONTEXT_CHUNKS,
            return_properties=["text"]
        )
        return " ".join(
            o.properties["text"][:MAX_CHARS_PER_CHUNK]
            for o in res.objects
        )

    # ---------------- TEXT ----------------
    def _generate_text_content(self, prompt):
        """Generate text content without caching - each request gets a fresh response"""
        generation_config = genai.types.GenerationConfig(
            temperature=0.7,
            max_output_tokens=2048,
            candidate_count=1
        )
        return self.text_model.generate_content(prompt, generation_config=generation_config)

    def generate_content(
        self,
        query=None,
        category_id=None,
        subpage=None,
        context=None,
        user_id=None
    ):
        telemetry = Telemetry()
        telemetry.mark("weaviate_ms")

        context_str = context or self.retrieve_context(query)
        max_lines = detect_max_lines_from_query(query)

        print("generate_content called with:")
        print(f"  - category_id: {category_id}")
        print(f"  - query: {query[:100] if query else 'None'}...")
        print(f"  - context length: {len(context_str)} chars")
        print(f"  - context preview: {context_str[:100] if context_str else 'EMPTY'}...")

        prompt = None


        # ---- ROUTING (UNCHANGED) ----
        if category_id == 2:
            prompt = build_full_understanding_prompt(
                query=query,
                context_str=context_str,
                topic=subpage,
                max_lines=max_lines
            )
        elif category_id == 3:
            prompt = build_project_case_study_prompt(
                query=query,
                context_str=context_str,
                project_sources={},
                max_lines=max_lines
            )
        elif category_id == 4:
            prompt = build_resource_prompt(
                query=query,
                context_str=context_str,
                resource_type="",
                sources="",
                max_lines=max_lines
            )
        elif category_id == 5:
            prompt = build_policy_prompt(
                query=query,
                context_str=context_str,
                param1="",
                param2="",
                max_lines=max_lines
            )
        elif category_id == 7:
            prompt = build_quarterly_newsletter_prompt(
                query=query,
                context_str=context_str,
                season="Winter",
                year="2026",
                max_lines=max_lines
            )

        telemetry.add_text_cost(prompt)
        
        print(f"Starting text generation for query: {query[:100]}...")  # Log first 100 chars

        try:
            future = self.executor.submit(
                self._generate_text_content,
                prompt
            )
            resp = future.result(timeout=TEXT_MODEL_TIMEOUT_SEC)
            print("Text generation completed successfully")
        except Exception as e:
            print(f"Error during text generation: {str(e)}")

        if resp and context_str and not max_lines:
            load_data_with_tracking(
                scraped_content=context_str,
                collection_name="training_data",
                user_id=user_id,
                source_url="RAG_GENERATION"
            )

        telemetry.mark("llm_ms")
        print(f"Generated text response length: {resp.text} chars")

        return resp.text, telemetry.export()

    # ---------------- IMAGE ----------------
    def _generate_image_content(self, final_prompt):
        """Generate image content without aggressive caching"""
        try:
            parts = [types.Part.from_text(text=final_prompt)]
            resp = self.image_client.models.generate_content(
                model=os.getenv("IMAGE_MODEL_ID"),
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"])
            )

            if not resp or not getattr(resp, "candidates", None):
                print("Image generation: No candidates in response")
                return None

            for part in resp.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    return base64.b64encode(part.inline_data.data).decode("utf-8")
                if hasattr(part, "image") and part.image:
                    return base64.b64encode(part.image.image_bytes).decode("utf-8")

            print("Image generation: No image data found in response parts")
            return None
        except Exception as e:
            print(f"Image generation error in _generate_image_content: {str(e)}")
            return None

    def generate_visual(
        self,
        prompt,
        context=None,
        ref_images_b64=None,
        force_style=None
    ):
        telemetry = Telemetry()
        telemetry.mark("image_ms")

        visual_mode = force_style or detect_visual_mode(prompt)
        final_prompt = build_image_prompt(
            query=prompt,
            context=context,
            style_key=visual_mode
        )

        try:
            if ref_images_b64:
                parts = [types.Part.from_text(text=final_prompt)]
                for img in ref_images_b64:
                    parts.append(
                        types.Part.from_bytes(
                            data=base64.b64decode(img),
                            mime_type="image/png"
                        )
                    )

                resp = self.image_client.models.generate_content(
                    model=os.getenv("IMAGE_MODEL_ID"),
                    contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"])
                )
                
                if resp and getattr(resp, "candidates", None):
                    for part in resp.candidates[0].content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            return base64.b64encode(part.inline_data.data).decode("utf-8")
                        if hasattr(part, "image") and part.image:
                            return base64.b64encode(part.image.image_bytes).decode("utf-8")
                return None
            else:
                return self._generate_image_content(final_prompt)

        except TimeoutError as e:
            telemetry.mark("image_timeout")
            print(f"Image generation timeout: {str(e)}")
            return None
        except OSError as e:
            telemetry.mark("image_network_error")
            print(f"Image generation network error (DNS/connection): {str(e)}")
            print("  - Check internet connectivity")
            print(f"  - Check IMAGE_MODEL_ID endpoint: {os.getenv('IMAGE_MODEL_ID')}")
            return None
        except Exception as e:
            telemetry.mark("image_error")
            print(f"Image generation error: {type(e).__name__}: {str(e)}")
            return None

        telemetry.mark("image_ms")
        return None

    # ---------------- ENTRY POINT ----------------
    def rag_entry_point(
        self,
        query,
        subpage=None,
        context_override=False,
        user_id=None,
        image_base_64=None,
        image_attachment_mode="text_only",
        category_id=None,
        context=None,
        prompt_session_id=None
    ):
        if image_attachment_mode == "text_only":
            text, telemetry = self.generate_content(
                query=query,
                category_id=category_id,
                subpage=subpage,
                context=context,
                user_id=user_id
            )
            return {
                "text": text,
                "images": [],
                "telemetry": telemetry
            }

        if image_attachment_mode == "image_only":
            image = self.generate_visual(
                prompt=query,
                context=context,
                ref_images_b64=image_base_64
            )
            return {
                "text": "",
                "images": [image] if image else [],
                "telemetry": None
            }

        if image_attachment_mode == "image_and_text":
            futures = {
                "text": self.executor.submit(
                    self.generate_content,
                    query=query,
                    category_id=category_id,
                    subpage=subpage,
                    context=context,
                    user_id=user_id
                ),
                "image": self.executor.submit(
                    self.generate_visual,
                    prompt=query,
                    context=context,
                    ref_images_b64=image_base_64
                )
            }

            telemetry = None
            text = None
            
            try:
                text, telemetry = futures["text"].result(timeout=TEXT_MODEL_TIMEOUT_SEC)
            except Exception as e:
                print(f"Error during text generation in image_and_text mode: {str(e)}")
            
            image = None
            try:
                image = futures["image"].result(timeout=IMAGE_MODEL_TIMEOUT_SEC)
            except Exception as e:
                print(f"Error during image generation in image_and_text mode: {str(e)}")

            print("Completed image_and_text generation")
            print(f"  - Generated text length: {text} ")
            print(f"  - Generated image present: {'Yes' if image else 'No'} ")

            return {
                "text": text,
                "images": [image] if image else [],
                "telemetry": telemetry
            }

        return {
            "text": UNREACHABLE_TEXT,
            "images": [],
            "telemetry": None
        }
