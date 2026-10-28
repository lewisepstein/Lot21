"""Free Form AI live web search: same triggers and research as Lot21 AI."""
import types

import pytest


@pytest.fixture
def ff(monkeypatch):
    import freeform_module.freeform_utils as fu
    import rag_module.rag as rag

    seen = {}

    def fake_generate(content, generation_config, system_instruction=None):
        seen["prompt"] = content
        seen["system"] = system_instruction
        return types.SimpleNamespace(text="Here is the answer.")

    monkeypatch.setattr(fu, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(fu, "FREEFORM_MODEL_ID", "test-model", raising=False)
    monkeypatch.setattr(fu, "generate_with_model_fallback", fake_generate)
    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", True)
    seen["searches"] = []

    def fake_search(client, model_id, query):
        seen["searches"].append(query)
        return (
            "- Fact A reported March 2026",
            [{"title": "Web: example.org", "url": "https://example.org/a"}],
        )

    monkeypatch.setattr(rag, "fetch_live_web_data", fake_search)
    return fu, seen


def test_trigger_prompt_searches_and_lists_sources(ff):
    fu, seen = ff
    text, image, kind = fu.generate_ai_response("Find the latest news on carbon removal in 2026")
    assert seen["searches"]
    assert "LIVE WEB DATA" in seen["prompt"] and "Fact A reported March 2026" in seen["prompt"]
    assert "do NOT have live internet" not in seen["system"]
    assert text.endswith("- Web: example.org: https://example.org/a")
    assert (image, kind) == (None, "TEXT")


def test_plain_prompt_does_not_search(ff):
    fu, seen = ff
    text, _, _ = fu.generate_ai_response("Write a short poem about trees")
    assert not seen["searches"]
    assert "LIVE WEB DATA" not in seen["prompt"]
    assert "do NOT have live internet" in seen["system"]
    assert "Sources:" not in text


def test_search_failure_still_answers(ff, monkeypatch):
    import rag_module.rag as rag

    fu, seen = ff

    def boom(*a, **k):
        raise RuntimeError("429 credits depleted")

    monkeypatch.setattr(rag, "fetch_live_web_data", boom)
    text, _, _ = fu.generate_ai_response("Find the latest news on carbon removal in 2026")
    assert text.startswith("Here is the answer.")
    assert "do NOT have live internet" in seen["system"]


@pytest.mark.parametrize("q", ["Update the website footer", "Write a LinkedIn post about trees", "Draft the newsletter intro"])
def test_partial_words_do_not_trigger_search(q, monkeypatch):
    import rag_module.rag as rag

    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", True)
    assert not rag.RagModule._should_use_web_search(q, None)


@pytest.mark.parametrize("q", ["Which searches found it?", "Find articles linked to the High Line", "What is currently built?"])
def test_word_endings_still_trigger_search(q, monkeypatch):
    import rag_module.rag as rag

    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", True)
    assert rag.RagModule._should_use_web_search(q, None)


def test_link_checks_run_in_parallel_within_a_time_limit(monkeypatch):
    import time

    import rag_module.rag as rag

    monkeypatch.setattr(rag, "LINK_CHECK_BUDGET_SEC", 0.5)
    slow = {"https://slow.example/a"}

    def checker(url):
        time.sleep(0.3 if url not in slow else 3)
        return True

    text = "A https://a.example/1 B https://b.example/2. C https://slow.example/a"
    start = time.monotonic()
    out = rag.RagModule._strip_unverified_urls(text, checker=checker)
    assert time.monotonic() - start < 1.5
    assert "https://a.example/1 B https://b.example/2. C" in out  # punctuation kept
    assert "slow.example" not in out and out.endswith("[link could not be verified and was removed]")


def test_free_form_search_has_an_overall_time_limit(monkeypatch):
    import time

    import freeform_module.freeform_utils as fu
    import rag_module.rag as rag

    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", True)
    monkeypatch.setattr(rag, "WEB_SEARCH_TIMEOUT_SEC", 0.3)
    monkeypatch.setattr(fu, "GEMINI_API_KEY", "test-key")
    called = []
    monkeypatch.setattr(rag, "fetch_live_web_data", lambda *a: called.append(1) or time.sleep(2) or ("late", []))
    start = time.monotonic()
    assert fu.fetch_web_context("Find the latest news on biochar") == ("", [])
    assert called and time.monotonic() - start < 1.5


def test_text_mode_does_not_claim_an_image(monkeypatch):
    import types

    import freeform_module.freeform_utils as fu

    seen = {}
    monkeypatch.setattr(fu, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(fu, "fetch_web_context", lambda msg: ("", []))
    monkeypatch.setattr(
        fu, "generate_with_model_fallback",
        lambda content, generation_config, system_instruction=None: seen.update(s=system_instruction) or types.SimpleNamespace(text="ok"),
    )
    fu.generate_ai_response("Create an image of a solar farm", mode="text")
    assert "never say you have generated" in seen["s"]


def test_free_form_links_are_clickable_and_safe():
    from pathlib import Path

    html = (Path(__file__).resolve().parent.parent / "app" / "templates" / "freeform.htm").read_text()
    assert "replace(/https?:\\/\\/[^\\s<]+/g" in html
    assert "url.replace(/\"/g, '&quot;')" in html
