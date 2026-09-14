"""
Checks for the Sept 2026 client-feedback fixes (Lot21 AI):
question routing, context merge, season/year parsing, image prompt rules,
image session memory, and the settings status endpoint.
"""
import types

import pytest


@pytest.fixture(scope="module")
def rag():
    import rag_module.rag as r

    return r


# ---------- season / year ----------

def test_date_range_does_not_pick_first_year(rag, monkeypatch):
    monkeypatch.delenv("NEWSLETTER_SEASON", raising=False)
    monkeypatch.delenv("NEWSLETTER_YEAR", raising=False)
    season, year = rag.detect_season_and_year(
        "Which newsletters feature concrete between the Fall/2023 and Spring/2026 issues?"
    )
    assert (season, year) != ("Spring", "2023")
    assert year != "2023"


def test_single_season_and_year_still_detected(rag, monkeypatch):
    monkeypatch.delenv("NEWSLETTER_SEASON", raising=False)
    monkeypatch.delenv("NEWSLETTER_YEAR", raising=False)
    assert rag.detect_season_and_year("Write the Summer 2026 newsletter") == ("Summer", "2026")


# ---------- question detection ----------

@pytest.mark.parametrize(
    "q",
    [
        "Which archived QUARTERLY newsletter included information on low-embodied-carbon concrete?",
        "When did we last cover timber construction?",
        "List the issues that mention concrete",
        "Is there a newsletter about mass timber?",
    ],
)
def test_questions_are_detected(rag, q):
    assert rag.is_question_query(q)


@pytest.mark.parametrize(
    "q",
    [
        "Write the Summer 2026 quarterly newsletter",
        "What is circularity?",  # content request, handled by category templates
        "refine it",
        "Generate three projects about adaptive reuse",
    ],
)
def test_content_requests_are_not_questions(rag, q):
    assert not rag.is_question_query(q)


# ---------- image prompt ----------

def test_overhead_request_uses_aerial_style_and_rules():
    from rag_module.image_prompts import build_image_prompt, detect_visual_mode

    q = "True aerial photograph, directly overhead, of a busy urban intersection"
    assert detect_visual_mode(q) == "aerial"
    prompt = build_image_prompt(q, "some page context", style_key="aerial")
    low = prompt.lower()
    assert "nadir" in low or "directly overhead" in low
    assert "human-scale" not in low
    assert "one single image" in low
    assert "no text" in low or "do not render any text" in low


def test_image_prompt_carries_previous_instructions():
    from rag_module.image_prompts import build_image_prompt

    history = [
        {"prompt": "Images must be taken directly overhead, no words or background.", "response": ""},
        {"prompt": "Provide a URL for each image.", "response": ""},
    ]
    prompt = build_image_prompt("three more images", "ctx", conversation_history=history)
    assert "directly overhead" in prompt


# ---------- routing inside generate_content ----------

def _bare_rag(rag, captured):
    from concurrent.futures import ThreadPoolExecutor

    obj = rag.RagModule.__new__(rag.RagModule)
    obj.executor = ThreadPoolExecutor(max_workers=1)
    obj.fallback_model_id = "test-fallback"
    obj._retrieve_chunks = lambda q: ("RETRIEVED NEWSLETTER TEXT about concrete", ())
    obj._resolve_source_labels = lambda doc_ids: []  # no database in unit tests

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return types.SimpleNamespace(text="ANSWER")

    obj._generate_text_content = fake_generate
    obj._generate_fallback_text_content = fake_generate
    return obj


def test_question_on_newsletter_page_is_answered_not_generated(rag, monkeypatch):
    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", False)
    monkeypatch.setattr(rag, "load_data_with_tracking", lambda **kw: None)
    captured = {}
    obj = _bare_rag(rag, captured)

    text, _, _, _ = obj.generate_content(
        query="Which archived QUARTERLY newsletter mentioned low-embodied-carbon concrete?",
        category_id=7,
        context="Archives newsletters Winter/2026 Spring/2026 Fall/2023",
    )
    prompt = captured["prompt"]
    assert "Which archived QUARTERLY newsletter" in prompt
    assert "quarterly banner" not in prompt.lower()
    # page context and knowledge base are both present
    assert "Winter/2026" in prompt
    assert "RETRIEVED NEWSLETTER TEXT" in prompt
    assert text == "ANSWER"


def test_page_context_is_merged_with_retrieval_for_generation(rag, monkeypatch):
    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", False)
    monkeypatch.setattr(rag, "load_data_with_tracking", lambda **kw: None)
    captured = {}
    obj = _bare_rag(rag, captured)
    obj.generate_content(
        query="Write the Summer 2026 quarterly newsletter",
        category_id=7,
        context="PAGE CONTEXT",
    )
    assert "PAGE CONTEXT" in captured["prompt"]
    assert "RETRIEVED NEWSLETTER TEXT" in captured["prompt"]


# ---------- settings status ----------

def test_api_status_reflects_environment(monkeypatch):
    from agent_module import agent

    monkeypatch.setenv("GEMINI_TEXT_API_KEY", "k")
    monkeypatch.setenv("GEMINI_IMAGE_API_KEY", "k")
    monkeypatch.setenv("IMAGE_MODEL_ID", "m")
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    status = agent.api_status()
    assert status == {"web_search_configured": True, "image_gen_configured": True}
    monkeypatch.delenv("GEMINI_IMAGE_API_KEY")
    assert agent.api_status()["image_gen_configured"] is False


# ---------- web search triggers, UI wording, user guide ----------

@pytest.mark.parametrize(
    "q",
    [
        "Research credible sources on embodied carbon in concrete",
        "Give me statistics on timber construction",
        "Find data on urban heat islands",
    ],
)
def test_research_asks_trigger_web_search_in_any_category(rag, q, monkeypatch):
    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", True)
    assert rag.RagModule._should_use_web_search(q, category_id=3)  # projects, not newsletter/policy


def test_plain_generation_does_not_trigger_web_search(rag, monkeypatch):
    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", True)
    assert not rag.RagModule._should_use_web_search("Write a case study about adaptive reuse", category_id=3)


def test_prompt_placeholder_invites_questions():
    from pathlib import Path

    html = Path("templates/content.htm").read_text()  # cwd is app/ (see conftest)
    assert "ask a question about this page" in html
    assert 'placeholder="Ask AI to refine, explain' not in html


def test_user_guide_documents_aerial_mode_and_image_limits():
    from pathlib import Path

    guide = Path("../Lottie_User_Guide.md").read_text()
    assert "### Aerial Mode" in guide
    for word in ("aerial", "overhead", "nadir"):
        assert f"**{word}**" in guide
    assert "one image per request" in guide
    assert "do not have a source URL" in guide
