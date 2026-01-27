# rag_engine.py
import os
import base64
from functools import lru_cache

from dotenv import load_dotenv
from service_utils.db_utils.weaviate_db import WeaviateDB
from weaviate_module.weaviate_utils import load_data_with_tracking

from rag_module.telemetry import Telemetry
from rag_module.understanding_prompts import build_full_understanding_prompt
from rag_module.case_study_prompts import build_project_case_study_prompt
from rag_module.resource_prompts import build_resource_prompt
from rag_module.policy_prompts import build_policy_prompt
from rag_module.newsletter_prompts import build_quarterly_newsletter_prompt


load_dotenv()

MAX_CONTEXT_CHUNKS = 6
MAX_CHARS_PER_CHUNK = 1200
CACHE_SIZE = 128

class RagModule:

    def __init__(self):
        self.client = WeaviateDB().client
        self.collection = self.client.collections.get("training_data")

        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_TEXT_API_KEY"))
        self.text_model = genai.GenerativeModel(
            os.getenv("TEXT_MODEL_ID", "gemini-3-flash-preview")
        )

        from google import genai as genai_new
        self.image_client = genai_new.Client(
            api_key=os.getenv("GEMINI_IMAGE_API_KEY"),
            http_options={"api_version": "v1beta"}
        )

    # ---------------- CONTEXT ----------------
    def retrieve_context(self, query: str):
        return self._retrieve_cached(query)

    @lru_cache(maxsize=CACHE_SIZE)
    def _retrieve_cached(self, query):
        res = self.collection.query.bm25(
            query=query,
            limit=MAX_CONTEXT_CHUNKS,
            return_properties=["text", "doc_id"]
        )
        return [
            {"content": o.properties["text"][:MAX_CHARS_PER_CHUNK],
             "doc_id": o.properties["doc_id"]}
            for o in res.objects
        ]

    def _context_str(self, contexts):
        return "\n\n".join(f"Context: {c['content']}" for c in contexts)

    # ---------------- TEXT ----------------
    def generate_content(
            self, 
            query = None, 
            category_id=None, 
            subpage=None, 
            context=None, 
            user_id=None
    ):
        telemetry = Telemetry()

        telemetry.mark("weaviate_ms")

        # context_str = self._context_str(self.retrieve_context(query))

        context_str = context if context is not None else ""  # Bypass context for now

        # Routing preserved
        if category_id == 1:
            topic = subpage
            prompt = build_full_understanding_prompt(query, context_str, topic)
        elif category_id == 2:
            prompt = build_project_case_study_prompt(query, context_str, {})
        elif category_id == 3:
            prompt = build_resource_prompt(query, context_str, "", "")
        elif category_id == 4:
            prompt = build_policy_prompt(query, context_str, "", "")
        else:
            prompt = build_quarterly_newsletter_prompt(query, context_str, season="Winter", year="2026")

        telemetry.add_text_cost(prompt)

        resp = self.text_model.generate_content(prompt)

        if resp:
            load_data_with_tracking(
                scraped_content=context_str, 
                collection_name="training_data", 
                user_id=user_id,
                source_url="RAG_GENERATION"
            )

        telemetry.mark("llm_ms")

        return resp.text, telemetry.export()


    # ---------------- IMAGE ----------------
    def generate_visual(self, prompt):
        if not self.image_client:
            return None

        try:
            from google.genai import types

            resp = self.image_client.models.generate_content(
                model=os.getenv("IMAGE_MODEL_ID"),
                contents=[prompt],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"])
            )

            # --- SAFE EXTRACTION ---
            if not resp or not hasattr(resp, "candidates") or not resp.candidates:
                return None

            candidate = resp.candidates[0]
            if not candidate or not hasattr(candidate, "content") or not candidate.content:
                return None

            parts = getattr(candidate.content, "parts", None)
            if not parts:
                return None

            for part in parts:
                # v1beta inline image data
                if hasattr(part, "inline_data") and part.inline_data:
                    return base64.b64encode(part.inline_data.data).decode("utf-8")

                # fallback image object
                if hasattr(part, "image") and part.image:
                    return base64.b64encode(part.image.image_bytes).decode("utf-8")

        except Exception as e:
            # IMPORTANT: do NOT crash the pipeline
            # Image generation is optional
            return None

        return None


    # ---------------- ENTRY POINT ----------------
    def rag_entry_point(self, 
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
        
        print(f"RAG Entry Point - Mode: {image_attachment_mode}")

        print("Context Override:", context)

        data = {}
        
        if image_attachment_mode == "text_only":
            # For text-only modes, skip RAG text generation

            text, telemetry = self.generate_content(
                query=query, category_id=category_id, subpage=subpage, context=context, user_id=user_id
            )

            data = {
                "text": text,
                "images": [],
                "telemetry": telemetry
            }
        
        elif image_attachment_mode == "image_only":
            # For image-only modes, do RAG text generation

            image = self.generate_visual(query)

            data = {
                "text": "",
                "images": [image] if image else [],
                "telemetry": None
            }

        elif image_attachment_mode == "image_and_text":

            text, telemetry = self.generate_content(
                query=query, category_id=category_id, subpage=subpage, context=context, user_id=user_id
            )

            image = self.generate_visual(query)

            data = {
                "text": text,
                "images": [image] if image else [],
                "telemetry": telemetry
            }

        return data
