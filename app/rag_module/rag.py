# rag_engine.py
import base64
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime
from functools import lru_cache

import google.generativeai as genai
from dotenv import load_dotenv
from google import genai as genai_new
from google.genai import types
from service_utils.db_utils.pg_db import PostgresDB
from service_utils.db_utils.weaviate_db import WeaviateDB
from sqlalchemy import text as sql_text
from weaviate_module.weaviate_utils import load_data_with_tracking

from rag_module.case_study_prompts import build_project_case_study_prompt
from rag_module.definition_prompt import build_definition_prompt
from rag_module.image_prompts import build_image_prompt, detect_visual_mode
from rag_module.intent_redirects import is_rewrite_intent
from rag_module.lots_prompts import build_lots_prompt
from rag_module.max_line_detector import (
    build_length_constraint,
    detect_max_lines_from_query,
    detect_sentence_limit,
)
from rag_module.newsletter_prompts import build_quarterly_newsletter_prompt
from rag_module.paragraph_rules import (
    build_paragraph_constraint,
    detect_target_paragraph,
    extract_paragraph_count,
)
from rag_module.policy_prompts import build_policy_prompt
from rag_module.prompt_rules import LottiePrompts
from rag_module.resource_prompts import build_resource_prompt
from rag_module.social_media_prompts import (
    build_social_media_campaign_prompt,
    build_social_media_post_prompt,
)
from rag_module.telemetry import Telemetry
from rag_module.understanding_prompts import build_full_understanding_prompt

load_dotenv()

# ---------------- CONFIG ----------------
TEXT_MODEL_TIMEOUT_SEC = 60  # Increased from 20 to 60 seconds
IMAGE_MODEL_TIMEOUT_SEC = 90  # Increased from 30 to 90 seconds

# Context depth per generation — richer context improves draft quality;
# Gemini's context window is far larger than even the raised values
MAX_CONTEXT_CHUNKS = int(os.getenv("RAG_MAX_CONTEXT_CHUNKS", "12"))
MAX_CHARS_PER_CHUNK = int(os.getenv("RAG_MAX_CHARS_PER_CHUNK", "2000"))
CACHE_SIZE = 128

# Hybrid search weighting: 0 = pure keyword (BM25), 1 = pure semantic (vector)
HYBRID_ALPHA = float(os.getenv("HYBRID_SEARCH_ALPHA", "0.5"))

# Live web search (Gemini Google Search grounding) — always on for categories
# whose content goes stale fast, plus any query that asks for current data
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
WEB_SEARCH_CATEGORY_IDS = {5, 7}  # 5 = policy, 7 = newsletter
WEB_SEARCH_TRIGGERS = (
    "latest",
    "current",
    "recent",
    "today",
    "this year",
    "this week",
    "news",
    "up to date",
    "up-to-date",
)

# Deduplication: sections that list projects must not repeat ones the user
# has already seen on the same page (case studies and lots/initiatives only —
# newsletters/policy legitimately reuse the same organizations)
DEDUP_ENABLED = os.getenv("DEDUP_ENABLED", "true").lower() in ("1", "true", "yes")
DEDUP_CATEGORY_IDS = {3, 6}

WEB_SEARCH_RESEARCH_PROMPT = (
    "Use Google Search to find the most current data available on the topic below. "
    "Return a concise fact sheet of 5-12 bullet points with concrete figures and dates, "
    "stating the month and year each fact was reported. No commentary.\n\nTopic: {query}"
)

UNREACHABLE_TEXT = (
    "We're having trouble reaching the AI agent right now. "
    "Your request wasn't lost. Please try again in a moment."
)

NETWORK_ERROR_TEXT = (
    "Unable to connect to the AI service due to network issues. "
    "Please check your internet connection and try again."
)

OUT_OF_SCOPE_TEXT = "This question is outside the scope of the provided context."

NO_CONTENT_TO_REFINE_TEXT = (
    "There's no content to refine yet. Please generate content first (describe "
    'what you\'d like me to create), then use commands like "refine it" or '
    '"make it shorter" to improve it.'
)

# Page-configured climate pillar -> case study category id
SUB_CATEGORY_IDS = {"ADAPT": 1, "MITIGATE": 2, "RESTORE": 3}

SEASON_BY_MONTH = {
    12: "Winter",
    1: "Winter",
    2: "Winter",
    3: "Spring",
    4: "Spring",
    5: "Spring",
    6: "Summer",
    7: "Summer",
    8: "Summer",
    9: "Fall",
    10: "Fall",
    11: "Fall",
}


def detect_season_and_year(query: str):
    """
    Season/year for newsletters: env override first (NEWSLETTER_SEASON /
    NEWSLETTER_YEAR), then whatever the query states, then the current date.
    """
    q = (query or "").lower()
    today = datetime.now()

    season = os.getenv("NEWSLETTER_SEASON")
    if not season:
        for name in ("winter", "spring", "summer", "autumn", "fall"):
            if name in q:
                season = "Fall" if name in ("autumn", "fall") else name.title()
                break
    if not season:
        season = SEASON_BY_MONTH[today.month]

    year = os.getenv("NEWSLETTER_YEAR")
    if not year:
        year_match = re.search(r"\b(20\d{2})\b", query or "")
        year = year_match.group(1) if year_match else str(today.year)

    return season, year


def detect_policy_scope(query: str) -> str:
    """
    Policy scope: env override (POLICY_SCOPE), else International when the
    query clearly points abroad, else National (the previous default).
    """
    env_scope = os.getenv("POLICY_SCOPE")
    if env_scope:
        return env_scope
    q = (query or "").lower()
    international_terms = (
        "international",
        "global",
        "worldwide",
        "ndc",
        "united nations",
        "paris agreement",
        "cop2",
        "cop3",
        "treaty",
    )
    if any(t in q for t in international_terms):
        return "International"
    return "National"


def detect_case_study_category(query: str, context_str: str = None) -> int:
    """
    Detects the specific Case Study category (Adapt/Mitigate/Restore)
    based on keywords in the user query; when the query gives no signal,
    the retrieved page context is scored before defaulting to Adapt.
    1: Adapt (Default)
    2: Mitigate
    3: Restore
    """
    if query:
        q = query.lower()

        # 3: Restore
        if any(
            k in q
            for k in [
                "restore",
                "restor",
                "nature",
                "biodiversity",
                "ecological",
                "rewild",
            ]
        ):
            return 3

        # 2: Mitigate
        if any(
            k in q
            for k in [
                "mitigate",
                "mitigat",
                "carbon",
                "reduction",
                "emission",
                "energy",
            ]
        ):
            return 2

    # Query gave no signal — let the page content decide before falling back
    if context_str:
        c = context_str.lower()
        scores = {
            3: sum(c.count(k) for k in ["restore", "restor", "biodiversity", "rewild"]),
            2: sum(
                c.count(k)
                for k in ["mitigat", "carbon reduction", "emission", "decarbon"]
            ),
            1: sum(c.count(k) for k in ["adapt", "resilien", "flood"]),
        }
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best

    # 1: Adapt (Default fallback)
    return 1


def is_follow_up_query(query: str) -> bool:
    """
    Lightweight intent check for multi-turn sessions: does this prompt build
    on the previous AI response (follow-up) or start something fresh?
    Only consulted when the session already has earlier exchanges, so a
    false positive merely includes harmless extra context.
    """
    if not query:
        return False
    q = f" {query.lower().strip()} "
    if is_rewrite_intent(query):
        return True
    # References to numbered items of a previous answer: "project 3", "item 7"
    if re.search(r"\b(project|item|point|entry|number|no\.?|#)\s*\d+\b", q):
        return True
    cues = (
        "this list",
        "the list",
        "that list",
        "the above",
        "above list",
        "previous response",
        "last response",
        "add ",
        "remove ",
        "replace ",
        "delete ",
        "drop ",
        "swap ",
        "instead",
        "another",
        "one more",
        " more ",
        " also ",
        " again ",
        " it ",
        " them ",
        " these ",
        " those ",
    )
    return any(c in q for c in cues)


# Verbs that, on their own, only make sense as edits of existing content
_EDIT_VERBS = {
    "refine",
    "refi",
    "rewrite",
    "rephrase",
    "reword",
    "revise",
    "edit",
    "polish",
    "improve",
    "enhance",
    "fix",
    "correct",
    "redo",
    "shorten",
    "condense",
    "simplify",
    "expand",
    "elaborate",
    "tighten",
    "reformat",
}
# Filler + quality adjectives that may accompany an edit verb without adding
# a topic of their own
_EDIT_FILLERS = {
    "it",
    "this",
    "that",
    "them",
    "these",
    "those",
    "the",
    "a",
    "an",
    "please",
    "again",
    "more",
    "less",
    "bit",
    "little",
    "up",
    "and",
    "by",
    "for",
    "me",
    "make",
    "keep",
    "content",
    "text",
    "response",
    "draft",
    "version",
    "one",
    "now",
    "some",
    # quality adjectives ("make it <adj>")
    "better",
    "concise",
    "shorter",
    "longer",
    "clearer",
    "clear",
    "formal",
    "informal",
    "professional",
    "simpler",
    "simple",
    "engaging",
    "readable",
    "brief",
    "detailed",
    "stronger",
    "smoother",
    "tighter",
    "cleaner",
    "punchy",
}


def is_contentless_edit_command(query: str) -> bool:
    """
    True when the prompt is a bare edit command with no subject matter of its
    own ("refine it", "make it better", "refi it better") — it can only be
    fulfilled against existing content. "write more about coastal adaptation"
    and "make it about renewable energy" are NOT contentless (they carry a
    topic), so they stay normal generations.
    """
    if not query:
        return False
    q = query.lower().strip()
    words = re.findall(r"[a-z]+", q)
    if not words or len(words) > 6:
        return False
    has_edit_signal = any(w in _EDIT_VERBS for w in words) or q.startswith(
        ("make it", "make this", "keep it")
    )
    if not has_edit_signal:
        return False
    return all(w in _EDIT_VERBS or w in _EDIT_FILLERS for w in words)


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
        self.text_model_id = text_model_id

        # Backup model — used only when the primary fails or returns empty
        self.fallback_model_id = os.getenv("TEXT_MODEL_FALLBACK_ID", "gemini-2.5-flash")
        self.fallback_text_model = genai.GenerativeModel(self.fallback_model_id)

        # Client for web-grounded generation (the Google Search tool needs the new SDK)
        self.search_client = genai_new.Client(api_key=text_api_key)

        # Configure image model
        image_api_key = os.getenv("GEMINI_IMAGE_API_KEY")
        image_model_id = os.getenv("IMAGE_MODEL_ID")

        if not image_api_key:
            print("WARNING: GEMINI_IMAGE_API_KEY not set in environment")
        if not image_model_id:
            print("WARNING: IMAGE_MODEL_ID not set in environment")

        print(f"Initializing image model: {image_model_id}")
        self.image_client = genai_new.Client(
            api_key=image_api_key, http_options={"api_version": "v1beta"}
        )

    # ---------------- CONTEXT ----------------
    @lru_cache(maxsize=CACHE_SIZE)
    def _retrieve_chunks(self, query: str):
        """Hybrid retrieval returning (joined_text, doc_ids of the chunks used)."""
        try:
            res = self.collection.query.hybrid(
                query=query,
                alpha=HYBRID_ALPHA,
                limit=MAX_CONTEXT_CHUNKS,
                return_properties=["text", "doc_id"],
            )
        except Exception as e:
            # Hybrid needs the vectorizer (Ollama); keyword search works without it
            print(f"WARNING: hybrid search failed ({e}), falling back to BM25")
            res = self.collection.query.bm25(
                query=query,
                limit=MAX_CONTEXT_CHUNKS,
                return_properties=["text", "doc_id"],
            )
        joined = " ".join(
            o.properties["text"][:MAX_CHARS_PER_CHUNK] for o in res.objects
        )
        doc_ids = tuple(
            dict.fromkeys(
                o.properties.get("doc_id")
                for o in res.objects
                if o.properties.get("doc_id")
            )
        )
        return joined, doc_ids

    def retrieve_context(self, query: str):
        return self._retrieve_chunks(query)[0]

    @staticmethod
    def _resolve_source_labels(doc_ids):
        """
        Map retrieval doc_ids to human-readable citations. Citations are
        best-effort: any failure returns what was resolved so far.
        """
        sources = []
        seen = set()
        try:
            db = PostgresDB()
            lookup = sql_text(
                "SELECT data_details->>'source_url' FROM weaviate_data "
                "WHERE data_details->>'doc_id' = :doc_id AND deleted_at IS NULL LIMIT 1"
            )
            for doc_id in doc_ids or ():
                if str(doc_id).startswith("approved_prompt_"):
                    title, url = "User-approved content", None
                else:
                    with db.engine.connect() as conn:
                        source_url = conn.execute(lookup, {"doc_id": doc_id}).scalar()
                    if source_url and source_url.startswith("http"):
                        title, url = source_url, source_url
                    else:
                        title, url = "Internal training data", None
                key = (title, url)
                if key not in seen:
                    seen.add(key)
                    sources.append({"title": title, "url": url})
        except Exception as e:
            print(f"Source label resolution failed (citations skipped): {e}")
        return sources

    # ---------------- TEXT ----------------
    def _generate_text_content(self, prompt):
        """Generate text content without caching - each request gets a fresh response"""
        generation_config = genai.types.GenerationConfig(
            temperature=0.9, max_output_tokens=8096, candidate_count=1
        )
        return self.text_model.generate_content(
            prompt, generation_config=generation_config
        )

    def _generate_fallback_text_content(self, prompt):
        """Same generation settings as the primary, on the backup model."""
        generation_config = genai.types.GenerationConfig(
            temperature=0.9, max_output_tokens=8096, candidate_count=1
        )
        return self.fallback_text_model.generate_content(
            prompt, generation_config=generation_config
        )

    @staticmethod
    def _safe_response_text(resp):
        """Extract response text; blocked/empty candidates raise on .text in this SDK."""
        try:
            return (resp.text or "") if resp else ""
        except Exception:
            return ""

    @staticmethod
    def _should_use_web_search(query, category_id):
        """Live search is on for fast-staling categories and 'current data' queries."""
        if not WEB_SEARCH_ENABLED:
            return False
        if category_id in WEB_SEARCH_CATEGORY_IDS:
            return True
        q = (query or "").lower()
        return any(trigger in q for trigger in WEB_SEARCH_TRIGGERS)

    @staticmethod
    def _build_research_topic(query, category_id):
        """
        What the live research should actually search for. Short edit
        instructions ("refine it", "polish this") carry no subject matter —
        searched verbatim they return junk (ore-refining, oil re-refining) —
        so fall back to the category's standing topic, or skip live search
        when there is none.
        """
        q = (query or "").strip()
        if q and not (is_rewrite_intent(q) and len(q.split()) <= 5):
            return q
        season, year = detect_season_and_year(q)
        if category_id == 7:
            return f"climate action, decarbonization and sustainable design news {season} {year}"
        if category_id == 5:
            scope = detect_policy_scope(q)
            return f"{scope} climate and environmental policy developments {year}"
        return None

    def _fetch_live_web_data(self, query):
        """
        Research step: grounded Gemini call that returns a current-data fact
        sheet, plus the web sources it cited.
        """
        resp = self.search_client.models.generate_content(
            model=self.text_model_id,
            contents=WEB_SEARCH_RESEARCH_PROMPT.format(query=query),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.5,
                max_output_tokens=2048,
            ),
        )
        gm = (
            resp.candidates[0].grounding_metadata
            if getattr(resp, "candidates", None)
            else None
        )
        searches = getattr(gm, "web_search_queries", None) or []
        print(f"Live web research ran {len(searches)} searches")

        web_sources = []
        seen = set()
        for grounding_chunk in getattr(gm, "grounding_chunks", None) or []:
            web = getattr(grounding_chunk, "web", None)
            uri = getattr(web, "uri", None) if web else None
            if not uri:
                continue
            title = getattr(web, "title", None) or uri
            # grounding redirect URIs are unique per chunk, so dedupe on the
            # displayed title (usually the domain) as well
            key = title.lower()
            if key not in seen:
                seen.add(key)
                web_sources.append({"title": f"Web: {title}", "url": uri})

        return (resp.text or "").strip(), web_sources

    def generate_content(
        self,
        query=None,
        category_id=None,
        subpage=None,
        context=None,
        user_id=None,
        rejected_feedback=None,
        sub_category=None,
        conversation_history=None,
        seen_items=None,
    ):
        telemetry = Telemetry()
        telemetry.mark("weaviate_ms")

        # A bare edit command ("refine it", "make it better") can only act on
        # existing content. With nothing to refine — no draft passed as context
        # and no prior exchange in this session — treating the command as a
        # topic makes the model invent a project named after the command
        # (e.g. a case study titled "REFI IT BETTER"). Refuse gracefully.
        if is_contentless_edit_command(query) and not (context or conversation_history):
            telemetry.mark("no_content_to_refine")
            print(
                "Edit command with no content to refine; asking user to generate first"
            )
            return NO_CONTENT_TO_REFINE_TEXT, telemetry.export(), [], 0

        sources = []
        if context:
            base_context = context
        else:
            base_context, retrieved_doc_ids = self._retrieve_chunks(query)
            sources.extend(self._resolve_source_labels(retrieved_doc_ids))
        context_str = base_context

        # Live web search: fetch current facts and fold them into the context —
        # prompt builders treat context as internal research, so even prompts
        # that say "use ONLY the internal research" will use the live data
        research_topic = (
            self._build_research_topic(query, category_id)
            if self._should_use_web_search(query, category_id)
            else None
        )
        if research_topic:
            try:
                future = self.executor.submit(self._fetch_live_web_data, research_topic)
                live_facts, web_sources = future.result(timeout=TEXT_MODEL_TIMEOUT_SEC)
                if live_facts:
                    sources.extend(web_sources)
                    context_str = (
                        base_context
                        + "\n\nLIVE WEB DATA (current figures fetched via Google Search"
                        + " — prefer these for statistics and recent events, and state"
                        + " their dates):\n"
                        + live_facts
                    )
                    telemetry.mark("websearch_ms")
                    print("Live web search ENABLED — current facts added to context")
            except Exception as web_error:
                print(
                    f"Live web research failed, continuing with training data only: {web_error}"
                )

        # Detect limits
        max_lines = detect_max_lines_from_query(query)
        sentence_limit = detect_sentence_limit(query)

        # Build the constraint string (prioritizes sentences if both exist)
        # Note: line_rule_str in the prompt calls below will now carry the strict message
        # We can pass this single string to prompts that accept 'line_rule' or similar.
        length_constraint_str = build_length_constraint(max_lines, sentence_limit)

        # Keep backward compatibility for prompt functions expecting line_rule_str
        line_rule_str = length_constraint_str

        is_rewrite = is_rewrite_intent(query)

        print("generate_content called with:")
        print(f"  - category_id: {category_id}")
        print(f"  - query: {query[:100] if query else 'None'}...")
        print(f"  - context length: {len(context_str)} chars")
        print(
            f"  - context preview: {context_str[:100] if context_str else 'EMPTY'}..."
        )

        prompt = None

        # Prioritize specific paragraph targeting
        target_paragraph = detect_target_paragraph(query)
        if target_paragraph:
            paragraphs = target_paragraph
        else:
            paragraphs = extract_paragraph_count(query)

        paragraph_rule = build_paragraph_constraint(paragraphs)

        has_line_constraint = max_lines is not None
        has_sentence_constraint = sentence_limit is not None

        # Multi-turn: a follow-up updates the previous response in this session
        # directly — category templates would reshape it into a fresh single
        # document or refuse it as out of scope. Focused paragraph rewrites
        # keep their existing dedicated path below.
        is_focused_rewrite = is_rewrite and (
            target_paragraph or "only" in (query or "").lower()
        )
        is_follow_up = bool(conversation_history) and is_follow_up_query(query)

        # A bare edit command ("refine it", "make it better") with content but
        # no session history: refine that content directly. Without this it
        # would fall to category generation, which treats the command as a
        # topic and produces a different project instead of refining.
        is_bare_refine = (
            is_contentless_edit_command(query) and bool(context) and not is_follow_up
        )

        # ---- ROUTING (category templates unchanged) ----
        if is_follow_up and not is_focused_rewrite:
            prompt = LottiePrompts.build_multi_turn_prompt(
                query=query,
                conversation_history=conversation_history,
                context_str=context_str,
                length_constraint=length_constraint_str,
            )
            telemetry.mark("multi_turn")
            print(
                f"Multi-turn follow-up: building on {len(conversation_history)} prior exchange(s)"
            )

        elif is_bare_refine:
            # Treat the existing content as a one-turn conversation so the
            # multi-turn prompt refines it in place — keeping the same
            # structure/format (title, year, source, narrative). The focused
            # rewrite prompt would strip that structure.
            synthetic_history = [
                {"prompt": "(the current content)", "response": base_context}
            ]
            prompt = LottiePrompts.build_multi_turn_prompt(
                query=query,
                conversation_history=synthetic_history,
                context_str="",
                length_constraint=length_constraint_str,
            )
            telemetry.mark("bare_refine")
            print(
                "Bare refine command with content: refining in place, structure preserved"
            )

        elif category_id == 2:
            if has_sentence_constraint:
                prompt = build_definition_prompt(
                    query=query, context_str=context_str, sentence_limit=sentence_limit
                )

            elif has_line_constraint:
                prompt = build_full_understanding_prompt(
                    query=query,
                    context_str=context_str,
                    topic=subpage,
                    max_lines=max_lines,
                    line_rule=line_rule_str,
                )

            elif is_rewrite and (target_paragraph or "only" in query.lower()):
                # Partial / Focused Rewrite (e.g. "Update paragraph 1", "Explain only financeability")
                prompt = LottiePrompts.build_focused_rewrite_prompt(
                    query=query,
                    target_section="CONTENT",
                    relevant_context=context_str,
                    paragraph_constraint=paragraph_rule,
                )

            else:
                # Global Update or New Generation -> ALWAYS Force Structure
                prompt = build_full_understanding_prompt(
                    query=query,
                    context_str=context_str,
                    topic=subpage,
                    max_lines=max_lines,
                    line_rule=line_rule_str,
                )

        elif category_id == 3:
            if is_rewrite and (target_paragraph or "only" in query.lower()):
                prompt = LottiePrompts.build_focused_rewrite_prompt(
                    query=query,
                    target_section="CONTENT",
                    relevant_context=context_str,
                    paragraph_constraint=paragraph_rule,
                )
            else:
                # The page's configured pillar wins; keyword/context detection
                # is only the fallback for unconfigured pages
                detected_cat = SUB_CATEGORY_IDS.get((sub_category or "").upper())
                if detected_cat:
                    print(f"Using page-configured sub-category: {sub_category}")
                else:
                    detected_cat = detect_case_study_category(query, context_str)
                prompt = build_project_case_study_prompt(
                    query=query,
                    context_str=context_str,
                    project_sources={},
                    category_id=detected_cat,
                    line_rule=line_rule_str,
                )

        elif category_id == 4:
            if is_rewrite and (target_paragraph or "only" in query.lower()):
                prompt = LottiePrompts.build_focused_rewrite_prompt(
                    query=query,
                    target_section="CONTENT",
                    relevant_context=context_str,
                    paragraph_constraint=paragraph_rule,
                )
            else:
                prompt = build_resource_prompt(
                    query=query,
                    context_str=context_str,
                    resource_type="",
                    sources="",
                    line_rule=line_rule_str,
                )

        elif category_id == 5:
            if is_rewrite and (target_paragraph or "only" in query.lower()):
                prompt = LottiePrompts.build_focused_rewrite_prompt(
                    query=query,
                    target_section="CONTENT",
                    relevant_context=context_str,
                    paragraph_constraint=paragraph_rule,
                )
            else:
                prompt = build_policy_prompt(
                    query=query,
                    context_str=context_str,
                    scope=detect_policy_scope(query),
                    sources="",
                    line_rule=line_rule_str,
                )

        elif category_id == 7:
            if is_rewrite and (target_paragraph or "only" in query.lower()):
                prompt = LottiePrompts.build_focused_rewrite_prompt(
                    query=query,
                    target_section="CONTENT",
                    relevant_context=context_str,
                    paragraph_constraint=paragraph_rule,
                )
            else:
                newsletter_season, newsletter_year = detect_season_and_year(query)
                prompt = build_quarterly_newsletter_prompt(
                    query=query,
                    context_str=context_str,
                    season=newsletter_season,
                    year=newsletter_year,
                    line_rule=line_rule_str,
                )

        # LOTS (new initiatives / projects / cards)
        elif category_id == 6:
            if is_rewrite and (target_paragraph or "only" in query.lower()):
                # Partial / Focused Rewrite
                prompt = LottiePrompts.build_focused_rewrite_prompt(
                    query=query,
                    target_section="CONTENT",
                    relevant_context=context_str,
                    paragraph_constraint=paragraph_rule,
                )
            else:
                # Global Update -> Force Structure
                prompt = build_lots_prompt(
                    query=query,
                    context_str=context_str,
                    topic=subpage,
                    max_lines=max_lines,
                    line_rule=line_rule_str,
                )

        # Social media content generation
        elif category_id == 8:
            if is_rewrite and (target_paragraph or "only" in query.lower()):
                prompt = LottiePrompts.build_focused_rewrite_prompt(
                    query=query,
                    target_section="CONTENT",
                    relevant_context=context_str,
                    paragraph_constraint=paragraph_rule,
                )
            else:
                platform = subpage if subpage else "x"
                prompt = build_social_media_post_prompt(
                    topic=query,
                    context_str=context_str,
                    platform=platform,
                    tone="informative",
                    length="short",
                )
                telemetry.mark("social_ms")

        # If we didn't build a prompt (unknown category or routing), return out-of-scope text
        if not prompt:
            print(
                "No prompt was constructed for this request; returning out-of-scope message."
            )
            telemetry.mark("llm_skipped")
            return OUT_OF_SCOPE_TEXT, telemetry.export(), [], 0

        # Rejection is a training signal: show recent rejected drafts of this
        # content so the model produces something meaningfully different
        if rejected_feedback:
            avoid_block = (
                "\n\nPREVIOUSLY REJECTED DRAFTS: The user rejected the following earlier "
                "draft(s) of this content. Generate a meaningfully different and better "
                "version; do not repeat their structure, phrasing, or weaknesses."
            )
            for i, item in enumerate(rejected_feedback, 1):
                avoid_block += f"\n\nRejected draft {i}"
                if item.get("note"):
                    avoid_block += f" (user note: {item['note']})"
                avoid_block += f":\n{item['text']}"
            prompt += avoid_block
            print(
                f"Added {len(rejected_feedback)} rejected draft(s) as avoidance signal"
            )

        # Dedup: projects the user has already seen on this page must not come
        # back as new items in project-list sections (case studies, lots).
        # Skipped on follow-ups — there the conversation history governs what to
        # keep/extend, and a "don't reintroduce these" rule would contradict it
        # (e.g. "add KPF to project 3" / "give me 5 more" need the existing list).
        excluded_seen = 0
        if DEDUP_ENABLED and seen_items and category_id in DEDUP_CATEGORY_IDS and not is_follow_up:
            excluded_seen = len(seen_items)
            prompt += (
                "\n\nPREVIOUSLY GENERATED PROJECTS (already shown to the user on "
                "this page in earlier generations):\n"
                + "; ".join(seen_items)
                + "\nSTRICT RULE: Do NOT introduce any of the projects above as new "
                "projects, case studies, or examples — pick different ones instead. "
                "They may only remain if the user's request edits existing content "
                "that already contains them."
            )
            telemetry.mark("dedup_filter")
            print(f"Dedup: excluding {excluded_seen} previously generated project(s)")

        telemetry.add_text_cost(prompt)

        print(
            f"Starting text generation for query: {query[:100]}..."
        )  # Log first 100 chars

        resp = None
        try:
            future = self.executor.submit(self._generate_text_content, prompt)
            resp = future.result(timeout=TEXT_MODEL_TIMEOUT_SEC)
            print("Text generation completed successfully")
        except Exception as e:
            print(f"Error during text generation: {str(e)}")

        # Automatic model fallback: one silent retry on the backup model when
        # the primary failed, timed out, or returned an empty/blocked response
        if not self._safe_response_text(resp).strip():
            print(
                f"Primary model gave no usable response; retrying with {self.fallback_model_id}"
            )
            try:
                future = self.executor.submit(
                    self._generate_fallback_text_content, prompt
                )
                resp = future.result(timeout=TEXT_MODEL_TIMEOUT_SEC)
                telemetry.mark("llm_fallback_model")
                print("Fallback model generation completed")
            except Exception as fallback_error:
                telemetry.mark("llm_error")
                print(f"Fallback model also failed: {str(fallback_error)}")

        # Re-ingest only the original context — web facts age fast, so they
        # should not be written into permanent training data. Best-effort:
        # a training-data write failure must never destroy the generated
        # response the user is waiting for.
        if resp and base_context and not max_lines:
            try:
                load_data_with_tracking(
                    scraped_content=base_context,
                    collection_name="training_data",
                    user_id=user_id,
                    source_url="RAG_GENERATION",
                )
            except Exception as ingest_error:
                telemetry.mark("reingest_failed")
                print(
                    f"Context re-ingestion failed (response still returned): {ingest_error}"
                )

        telemetry.mark("llm_ms")

        # Log full response length and content
        response_text = self._safe_response_text(resp)
        # If the model returned an empty body, surface a friendly error message
        if not response_text or not response_text.strip():
            telemetry.mark("llm_empty_response")
            print("AI returned an empty response; substituting UNREACHABLE_TEXT")
            response_text = UNREACHABLE_TEXT

        response_length = len(response_text)
        print(f"\n{'=' * 80}")
        print(f"RESPONSE GENERATED - Length: {response_length} chars")
        print(f"{'=' * 80}")
        print(f"FULL RESPONSE TEXT:\n{response_text}")
        print(f"{'=' * 80}\n")

        return response_text, telemetry.export(), sources, excluded_seen

    # ---------------- IMAGE ----------------
    def _generate_image_content(self, final_prompt):
        """Generate image content without aggressive caching"""
        try:
            parts = [types.Part.from_text(text=final_prompt)]
            resp = self.image_client.models.generate_content(
                model=os.getenv("IMAGE_MODEL_ID"),
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
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
        self, prompt, context=None, ref_images_b64=None, force_style=None
    ):
        telemetry = Telemetry()
        telemetry.mark("image_ms")

        visual_mode = force_style or detect_visual_mode(prompt)
        final_prompt = build_image_prompt(
            query=prompt, context=context, style_key=visual_mode
        )

        try:
            if ref_images_b64:
                parts = [types.Part.from_text(text=final_prompt)]
                for img in ref_images_b64:
                    parts.append(
                        types.Part.from_bytes(
                            data=base64.b64decode(img), mime_type="image/png"
                        )
                    )

                resp = self.image_client.models.generate_content(
                    model=os.getenv("IMAGE_MODEL_ID"),
                    contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
                )

                if resp and getattr(resp, "candidates", None):
                    for part in resp.candidates[0].content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            return base64.b64encode(part.inline_data.data).decode(
                                "utf-8"
                            )
                        if hasattr(part, "image") and part.image:
                            return base64.b64encode(part.image.image_bytes).decode(
                                "utf-8"
                            )
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
        prompt_session_id=None,
        rejected_feedback=None,
        sub_category=None,
        conversation_history=None,
        seen_items=None,
    ):
        if image_attachment_mode == "text_only":
            text, telemetry, sources, excluded_seen = self.generate_content(
                query=query,
                category_id=category_id,
                subpage=subpage,
                context=context,
                user_id=user_id,
                rejected_feedback=rejected_feedback,
                sub_category=sub_category,
                conversation_history=conversation_history,
                seen_items=seen_items,
            )
            return {
                "text": text,
                "images": [],
                "telemetry": telemetry,
                "sources": sources,
                "excluded_seen": excluded_seen,
            }

        if image_attachment_mode == "image_only":
            image = self.generate_visual(
                prompt=query, context=context, ref_images_b64=image_base_64
            )
            return {
                "text": "",
                "images": [image] if image else [],
                "telemetry": None,
                "sources": [],
                "excluded_seen": 0,
            }

        if image_attachment_mode == "image_and_text":
            futures = {
                "text": self.executor.submit(
                    self.generate_content,
                    query=query,
                    category_id=category_id,
                    subpage=subpage,
                    context=context,
                    user_id=user_id,
                    rejected_feedback=rejected_feedback,
                    sub_category=sub_category,
                    conversation_history=conversation_history,
                    seen_items=seen_items,
                ),
                "image": self.executor.submit(
                    self.generate_visual,
                    prompt=query,
                    context=context,
                    ref_images_b64=image_base_64,
                ),
            }

            telemetry = None
            text = None
            sources = []
            excluded_seen = 0

            try:
                text, telemetry, sources, excluded_seen = futures["text"].result(
                    timeout=TEXT_MODEL_TIMEOUT_SEC
                )
            except Exception as e:
                print(f"Error during text generation in image_and_text mode: {str(e)}")

            image = None
            try:
                image = futures["image"].result(timeout=IMAGE_MODEL_TIMEOUT_SEC)
            except Exception as e:
                print(f"Error during image generation in image_and_text mode: {str(e)}")

            print("Completed image_and_text generation")
            print(f"  - Generated text length: {len(text) if text else 0} chars")
            print(f"  - Generated image present: {'Yes' if image else 'No'} ")

            return {
                "text": text,
                "images": [image] if image else [],
                "telemetry": telemetry,
                "sources": sources,
                "excluded_seen": excluded_seen,
            }

        return {
            "text": UNREACHABLE_TEXT,
            "images": [],
            "telemetry": None,
            "sources": [],
            "excluded_seen": 0,
        }
