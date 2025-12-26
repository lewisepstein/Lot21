from service_utils.log_management import get_logger
from service_utils.db_utils.weaviate_db import WeaviateDB
from typing import Tuple
import os
from openai import OpenAI
    

# Set up logging
logger = get_logger(__name__)

# OpenAI configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


class RagModule:
    """RAG helper that wraps a Weaviate DB client and an LLM.

    This class provides:
    - retrieve_context(query, limit, alpha)
    - generate_content(query)


    Features:
    - Pure BM25 keyword retrieval from 'training_data' collection
    - Smart prompt routing: full "Understanding" article OR single section rewrite
    - Supports category parameter (e.g., "understanding", "section:durability")
    - Detects section rewrite intent from query text
    - Returns (content, explanation) tuple — content first for primary use
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
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not found in environment variables or .env file")
            
            if OpenAI is not None:
                self.llm = OpenAI(api_key=OPENAI_API_KEY)
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

            contexts = []
            for obj in response.objects:
                text = obj.properties.get("text", "").strip()
                if text:
                    # Truncate long chunks for prompt efficiency
                    snippet = text if len(text) < 1500 else text[:1500] + "..."
                    contexts.append(snippet)

            formatted = "\n\n".join(f"Context {i+1}: {ctx}" for i, ctx in enumerate(contexts))
            logger.info(f"Retrieved {len(contexts)} contexts for query: {query[:60]}...")
            return formatted if formatted else "No relevant context found."

        except Exception as e:
            logger.error(f"Error retrieving context from Weaviate: {e}")
            return ""


    def generate_content(self, query: str, category: str = "understanding") -> Tuple[str, str]:
        """
        Generate content with smart routing.

        Returns:
            (content: str, explanation: str)
            - content: Main article or rewritten section (primary output)
            - explanation: LLM's note on sources used, changes, assumptions
        """
        logger.info(f"Generating content | Query: {query[:60]}... | Category: {category}")

        if not self.llm:
            logger.error("LLM client not available")
            return None, "LLM not initialized"

        context_str = self.retrieve_context(query=query, limit=8)

        prompt = self._build_prompt(query=query, context_str=context_str, category=category)

        try:
            response = self.llm.chat.completions.create(
                model="gpt-4o",  
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1800,
            )
            raw_response = response.choices[0].message.content.strip()

            content, explanation = self._split_content_and_explanation(raw_response)

            logger.info(f"Generation complete | Content: {len(content)} chars | Explanation: {len(explanation)} chars")
            return content, explanation

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return "", f"Error during generation: {str(e)}"

    def _build_prompt(self, query: str, context_str: str, category: str) -> str:
        """Smart prompt routing: full article vs section rewrite."""
        query_lower = query.lower()
        category_lower = category.lower()

        # Explicit section rewrite via category
        if category_lower.startswith("section:"):
            target = self._normalize_section_name(category_lower.replace("section:", "").strip())
            relevant_context = context_str  # Pass all context; LLM will focus
            return self._build_section_rewrite_prompt(query, target, relevant_context)

        # Detect section rewrite intent from query
        if any(phrase in query_lower for phrase in ["only", "just", "rewrite the", "summarize the", "focus on", "improve the"]):
            target = self._detect_target_section(query_lower)
            relevant_context = context_str
            return self._build_section_rewrite_prompt(query, target, relevant_context)

        # Default: Full Understanding article
        if category_lower in ["understanding", ""]:
            return self._build_full_understanding_prompt(query, context_str)

        # Future categories (easy to extend)
        if category_lower == "project":
            return "Project content generation coming soon..."
        if category_lower == "resource":
            return "Resource summary coming soon..."
        if category_lower == "policies":
            return "Policy analysis coming soon..."

        # Fallback
        return self._build_full_understanding_prompt(query, context_str)

    def _build_full_understanding_prompt(self, query: str, context_str: str) -> str:
        return f"""
You are an expert content writer for Lot21 — a human welfare and climate justice platform.

{query}

Generate the article in PLAIN TEXT format only. 
DO NOT use any Markdown formatting:
- No bold, italics, or underlines
- No headers with #
- No bullet points with - or *
# - No numbered lists with 1. 2. etc.
- No separators like ---

Use simple, clean paragraphs. For lists, write them naturally in sentences using words like "first", "second", etc.
Style: Warm, professional, hopeful, solution-oriented. Use short paragraphs and natural lists.

Relevant Knowledge from Lottie Archives:
{context_str}

Important: Output ONLY the article content. Do not add any explanation, notes, or additional sections after the article.

"""

    def _build_section_rewrite_prompt(self, query: str, target_section: str, relevant_context: str) -> str:
        return f"""
You are an expert editor for Lot21 content.

Task: Rewrite ONLY the '{target_section}' section based on the query and available context.
Do NOT include any other sections or full article structure.
Output in PLAIN TEXT format only:
- No Markdown formatting
- No bold, bullets, numbers, or headers
- No separators

Write in natural, flowing paragraphs.
Query: {query}

Original/Available Context for this section:
{relevant_context if relevant_context else "No specific context found."}

Instructions:
- Maintain Lottie warm, professional, hopeful, and solution-oriented tone
- Use short paragraphs
- Improve clarity, flow, and engagement
- Output ONLY the rewritten section content

Important: Output ONLY the rewritten section. Do not add any explanation, notes, or additional text after it.
"""

    def _normalize_section_name(self, raw: str) -> str:
        mapping = {
            "how-it-works": "How It Works",
            "how_it_works": "How It Works",
            "howitworks": "How It Works",
            "how it works": "How It Works",
            "durability": "Durability",
            "financeability": "Financeability",
            "scalability": "Scalability",
            "equity": "Equity",
            "conclusion": "Conclusion",
        }
        return mapping.get(raw.lower(), raw.title())

    def _detect_target_section(self, query_lower: str) -> str:
        section_keywords = {
            "how it works": "How It Works",
            "durability": "Durability",
            "financeability": "Financeability",
            "scalability": "Scalability",
            "equity": "Equity",
            "conclusion": "Conclusion",
        }
        for keyword, name in section_keywords.items():
            if keyword in query_lower:
                return name
        return "Durability"  # sensible default

    def _split_content_and_explanation(self, raw: str) -> Tuple[str, str]:
        """Return only the content (no explanation needed anymore)."""
        content = raw.strip()
        return content, ""