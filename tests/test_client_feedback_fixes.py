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
        "Please tell me which newsletter covered concrete",
        "Can you find which issue mentioned concrete?",
        "Could you please list the issues on timber",
        "I want to know when we last covered biochar",
        "Search the archive for issues mentioning concrete",
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


# ---------- session history keeps image-only turns ----------

def test_conversation_history_keeps_image_only_turns():
    import json
    from content_module import prompt_history_utils as phu

    rows = [  # newest first, as the database returns them
        {"user_prompt": "Provide three more images", "ai_response": json.dumps({"text": "", "images": ["s3://b"]})},
        {"user_prompt": "Images must be taken directly overhead, no words.", "ai_response": json.dumps({"text": "", "images": ["s3://a"]})},
        {"user_prompt": "placeholder without response", "ai_response": None},
    ]

    class FakeDB:
        def read(self, *a, **kw):
            return rows

    turns = phu._get_conversation_history(FakeDB(), "session-1")
    assert [t["prompt"] for t in turns] == [
        "Images must be taken directly overhead, no words.",
        "Provide three more images",
    ]
    assert all(t["response"] == "(image generated)" for t in turns)


# ---------- Projects research fixes (October 2026) ----------

LEW_LOOKUPS = [
    "Use internal training data plus internet search to find and list the names and URLs for all design journals that have covered this project: SHENZHEN BAY SPONGE WATERFRONT.",
    "Use an internet search to list the names and URLs for all design journals that have covered this project: SHENZHEN BAY SPONGE WATERFRONT. No descriptions are requested. Only respond with the listings.",
    "ONLY provide a link to the specific article about the SHENZHEN BAY SPONGE WATERFRONT project that was covered by The World Around. Provide nothing else.",
    "Was the Shenzhen Bay Sponge Waterfront project completed in 2026?",
    "Verify whether the Shenzhen Bay Sponge Waterfront project was completed and what remains in development.",
]

STILL_GENERATE = [
    "Using the same format, and without repeating the introductory statement, provide 5 more companies that transform captured carbon emissions into biodegradable plastics.",
    "Provide a case study on the Shenzhen Bay Sponge Waterfront project",
    "Find 5 new restore projects in Asia",
    "Write the Summer 2026 quarterly newsletter",
    "What is circularity?",
    "Generate three projects about adaptive reuse",
    "refine it",
]


def test_internet_wording_and_years_trigger_web_search_in_projects(rag, monkeypatch):
    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", True)
    for q in LEW_LOOKUPS:
        assert rag.RagModule._should_use_web_search(q, 3), q
    assert not rag.RagModule._should_use_web_search("Write a case study about adaptive reuse", 3)


def test_lookup_requests_are_answered_directly(rag):
    for q in LEW_LOOKUPS:
        assert rag.is_question_query(q), q


def test_generation_requests_still_generate(rag):
    for q in STILL_GENERATE:
        assert not rag.is_question_query(q), q


def test_the_listings_is_not_a_follow_up_but_edits_are(rag):
    assert not rag.is_follow_up_query(LEW_LOOKUPS[1])
    assert rag.is_follow_up_query("Add KPF as the lead design firm for project 3")
    assert rag.is_follow_up_query("remove project 7 from the list")
    assert rag.is_follow_up_query("give me 5 more projects not on this list")


def test_research_prompt_matches_the_question(rag):
    p = rag.RagModule._research_prompt(LEW_LOOKUPS[1])
    assert "URL" in p and "publication" in p.lower()
    p = rag.RagModule._research_prompt(LEW_LOOKUPS[3])
    assert "status" in p.lower() and "completion" in p.lower()
    p = rag.RagModule._research_prompt("latest statistics on embodied carbon in concrete")
    assert "fact sheet" in p


def test_static_links_are_background_only():
    from rag_module.static_links import get_links_as_string
    from rag_module.case_study_prompts import build_project_case_study_prompt

    s = get_links_as_string(["projects"])
    assert "background only" in s.lower() and "do not cite" in s.lower()
    p = build_project_case_study_prompt(query="x", context_str="", project_sources={}, category_id=3)
    assert "ADDITIONAL RESEARCH SOURCES" not in p


def test_new_project_requests_exclude_existing_lot21_listings(rag, monkeypatch):
    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", False)
    monkeypatch.setattr(rag, "load_data_with_tracking", lambda **kw: None)
    captured = {}
    obj = _bare_rag(rag, captured)
    obj.generate_content(query="Provide 5 new restore projects not already on Lot21", category_id=3, context="EXISTING PAGE TEXT")
    assert "EXISTING LOT21 LISTINGS" in captured["prompt"]
    obj.generate_content(query="Write a case study on the Shenzhen Bay Sponge Waterfront project", category_id=3, context="EXISTING PAGE TEXT")
    assert "EXISTING LOT21 LISTINGS" not in captured["prompt"]


def test_illustration_wording_selects_editorial_style():
    from rag_module.image_prompts import detect_visual_mode

    assert detect_visual_mode("Illustration of a coastal park in the style of the attached references") == "editorial"
    assert detect_visual_mode("watercolour drawing of a green roof") == "editorial"
    assert detect_visual_mode("photograph of a green roof") == "photo"


def test_dead_links_are_removed_from_live_research(rag):
    text = ("The World Around: https://theworldaround.org/project/shenzhen-bay-sponge-waterfront/ (May 2024)\n"
            "Dezeen: https://www.dezeen.com/real-article/ (2023)")
    alive = {"https://www.dezeen.com/real-article/": True,
             "https://theworldaround.org/project/shenzhen-bay-sponge-waterfront/": False}
    out = rag.RagModule._strip_unverified_urls(text, checker=lambda u: alive[u])
    assert "https://www.dezeen.com/real-article/" in out
    assert "shenzhen-bay-sponge-waterfront" not in out
    assert "could not be verified" in out


def test_answer_prompt_forbids_constructed_urls():
    from rag_module.prompt_rules import LottiePrompts

    p = LottiePrompts.build_answer_prompt("Only provide the link", "ctx")
    assert "Never construct, guess or complete a URL" in p


# ---------- prompt history pages require a session ----------

@pytest.mark.asyncio
async def test_prompt_history_pages_redirect_without_session(client):
    for path in ("/user/prompt_history_data", "/user/prompt_history_data/some-session-id"):
        r = await client.get(path)
        assert r.status_code == 302, path
        assert r.headers["location"] == "/"


@pytest.mark.asyncio
async def test_prompt_history_page_rejects_bogus_session(client):
    r = await client.get("/user/prompt_history_data", cookies={"session_token": "not-a-real-session"})
    assert r.status_code != 200
    assert "user_prompt" not in r.text


# ---------- private S3: links are signed on the way out ----------

@pytest.fixture
def aws(monkeypatch):
    from service_utils import aws_services as a

    monkeypatch.setattr(a, "AWS_S3_BUCKET", "lottie-test-bucket")
    monkeypatch.setattr(a, "AWS_REGION", "us-east-2")
    monkeypatch.setattr(a, "AWS_ACCESS_KEY", "AKIATEST")
    monkeypatch.setattr(a, "AWS_SECRET_KEY", "secret")
    return a


def test_presign_signs_only_our_bucket(aws):
    url = "https://lottie-test-bucket.s3.us-east-2.amazonaws.com/generated/generated_images/a.png"
    signed = aws.presign_s3_url(url)
    assert signed.startswith(url + "?")
    assert "X-Amz-Signature" in signed and "X-Amz-Expires=21600" in signed
    assert aws.presign_s3_url("https://example.com/x.png") == "https://example.com/x.png"
    assert aws.presign_s3_url(None) is None


def test_sign_ai_response_handles_string_and_dict(aws):
    import json

    url = "https://lottie-test-bucket.s3.us-east-2.amazonaws.com/generated/generated_images/a.png"
    raw = json.dumps({"text": "hello", "images": [url], "sources": None})
    out = json.loads(aws.sign_ai_response(raw))
    assert out["text"] == "hello" and "X-Amz-Signature" in out["images"][0]
    assert "X-Amz-Signature" in aws.sign_ai_response({"text": "", "images": [url]})["images"][0]
    assert aws.sign_ai_response("plain text answer") == "plain text answer"
    assert aws.sign_ai_response(json.dumps({"text": "no images", "images": None})) == json.dumps({"text": "no images", "images": None})


def test_document_export_fetches_signed_link(aws, monkeypatch):
    from download_module import document_builder as db

    seen = {}

    class R:
        content = b"png"
        def raise_for_status(self): pass

    monkeypatch.setattr(db.requests, "get", lambda url, timeout: seen.setdefault("url", url) and R())
    db._fetch_image("https://lottie-test-bucket.s3.us-east-2.amazonaws.com/generated/generated_images/a.png")
    assert "X-Amz-Signature" in seen["url"]


# ---------- 28-Oct QA fails: PR-02, RG-05 ----------

def test_what_is_status_question_is_a_lookup_not_a_rewrite(rag):
    # PR-02: "what is" read as a rewrite, so the page was rewritten instead
    q = "What is the current status of the Shenzhen Bay Sponge Waterfront project? Which phases are completed?"
    assert not rag.is_rewrite_intent(q)
    assert not rag.is_follow_up_query(q)
    assert rag.is_question_query(q)
    assert not rag.is_question_query("What is circularity?")


def test_overhead_style_carries_to_next_image_in_session():
    # RG-05: the second image fell back to the eye-level photo style
    from rag_module.image_prompts import detect_visual_mode

    history = [{"prompt": "Images must be taken directly overhead, no words.", "response": ""}]
    assert detect_visual_mode("Provide another image of a rooftop farm", history) == "aerial"
    assert detect_visual_mode("Now show a wetland boardwalk", history) == "aerial"
    # Watercolour asked for now wins; diagram words earlier do not leak
    assert detect_visual_mode("Watercolour of a rooftop farm", history) == "editorial"
    assert detect_visual_mode("A rooftop farm", [{"prompt": "Explain the water flow system", "response": ""}]) == "photo"
    assert detect_visual_mode("A rooftop farm") == "photo"
