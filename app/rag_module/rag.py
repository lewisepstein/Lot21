from service_utils.log_management import get_logger
from service_utils.db_utils.weaviate_db import WeaviateDB

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# Set up logging
logger = get_logger(__name__)


class RagModule:
    """RAG helper that wraps a Weaviate DB client and an LLM.

    This class provides:
    - retrieve_context(query, limit, alpha)
    - generate_content(query)
    """

    def __init__(self):
        # Initialize Weaviate first; keep client even if OpenAI initialization fails
        try:
            self.weaviate_db = WeaviateDB()
            self.client = getattr(self.weaviate_db, "client", None)
            logger.info("Weaviate client initialized in RagModule")
        except Exception as e:
            logger.error(f"Failed to initialize WeaviateDB in RagModule: {e}")
            self.client = None

        # Initialize OpenAI/LLM separately; failures should not unset Weaviate client
        try:
            if OpenAI is not None:
                self.llm = OpenAI()
                logger.info("OpenAI client initialized in RagModule")
            else:
                self.llm = None
                logger.warning("OpenAI SDK not available; LLM disabled in RagModule")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client in RagModule: {e}")
            self.llm = None

    def retrieve_context(
        self,
        query: str = "",
        limit: int = 5,
        alpha: float = 0.5,
    ) -> str:
        if not self.client:
            logger.error("Weaviate client is not initialized.")
            return ""

        try:
            collection = self.client.collections.get("training_data")

            response = collection.query.hybrid(
                query=query,
                alpha=alpha,
                limit=limit,
                return_properties=["text"],
            )

            return "\n".join(
                (obj.properties.get("text") or "") for obj in response.objects
            )
        except Exception as e:
            logger.error(f"Error retrieving context from Weaviate: {e}")
            return ""


    def generate_content(self, query: str) -> str:
        """Generate content using LLM and retrieved context.

        Accepts keyword `query` so callers using `generate_content(query=...)` work.
        """
        logger.info("=== Starting Lot21 Content Generator ===")

        if not self.client:
            logger.error("Weaviate client is not initialized.")
            return ""

        context = self.retrieve_context(query=query)

        prompt = f"""
You are an AI assistant.
Answer the question ONLY using the context below.

Context:
{context}

Question:
{query}
"""

        if not self.llm:
            logger.error("LLM client is not available (OpenAI import failed). Returning empty response.")
            return ""

        try:
            response = self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )

            # Be defensive in case response structure varies
            try:
                return response.choices[0].message.content
            except Exception:
                # Fallback for different SDK shapes
                return getattr(response, 'text', '') or str(response)
        except Exception as e:
            logger.error(f"Error generating content with LLM: {e}")
            return ""