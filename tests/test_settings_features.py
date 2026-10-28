"""
Approved Oct 2026 work: standing instructions, training from a URL, the
restored Lot21 AI Attach button and whole-word image keyword matching.
"""
import types
from pathlib import Path

import pytest
import requests

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"


# ---------- standing instructions ----------

class FakeDB:
    def __init__(self, rows=None, fail=False):
        self.rows, self.fail, self.updated = rows or [], fail, None

    def read(self, table, conditions=None, columns=None):
        if self.fail:
            raise RuntimeError("column standing_instructions does not exist")
        return self.rows

    def update(self, table, data, conditions):
        self.updated = (table, data, conditions)
        return []


def test_block_is_empty_without_saved_instructions(monkeypatch):
    import agent_module.standing_instructions as si

    monkeypatch.setattr(si, "PostgresDB", lambda: FakeDB([{"standing_instructions": None}]))
    assert si.standing_instructions_block(5) == ""
    assert si.standing_instructions_block(None) == ""


def test_block_carries_saved_instructions(monkeypatch):
    import agent_module.standing_instructions as si

    monkeypatch.setattr(si, "PostgresDB", lambda: FakeDB([{"standing_instructions": "  Always list sources.  "}]))
    block = si.standing_instructions_block(5)
    assert "STANDING INSTRUCTIONS" in block and block.endswith("Always list sources.")
    assert "the request wins" in block


def test_read_failure_never_blocks_generation(monkeypatch):
    import agent_module.standing_instructions as si

    monkeypatch.setattr(si, "PostgresDB", lambda: FakeDB(fail=True))
    assert si.get_standing_instructions(5) == ""


def test_save_trims_clears_and_limits(monkeypatch):
    import agent_module.standing_instructions as si

    db = FakeDB()
    monkeypatch.setattr(si, "PostgresDB", lambda: db)
    assert si.save_standing_instructions(5, "  Ask before summarising. ") == "Ask before summarising."
    assert db.updated == ("users", {"standing_instructions": "Ask before summarising."}, {"id": 5})
    si.save_standing_instructions(5, "   ")
    assert db.updated[1] == {"standing_instructions": None}
    with pytest.raises(ValueError):
        si.save_standing_instructions(5, "x" * 4001)


def test_lot21_ai_prompt_includes_standing_instructions(monkeypatch):
    import rag_module.rag as rag
    from test_client_feedback_fixes import _bare_rag

    monkeypatch.setattr(rag, "WEB_SEARCH_ENABLED", False)
    monkeypatch.setattr(rag, "load_data_with_tracking", lambda **kw: None)
    monkeypatch.setattr(
        rag, "standing_instructions_block",
        lambda uid: "\n\nSTANDING INSTRUCTIONS (saved):\nAlways list sources." if uid == 7 else "",
    )
    captured = {}
    _bare_rag(rag, captured).generate_content(
        query="Write the Fall 2026 newsletter", category_id=7, context="ctx", user_id=7
    )
    assert captured["prompt"].endswith("Always list sources.")


def test_free_form_system_prompt_includes_standing_instructions(monkeypatch):
    import freeform_module.freeform_utils as fu

    seen = {}

    def fake_generate(content, generation_config, system_instruction=None):
        seen["system"] = system_instruction
        return types.SimpleNamespace(text="ok")

    monkeypatch.setattr(fu, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(fu, "generate_with_model_fallback", fake_generate)
    monkeypatch.setattr(fu, "fetch_web_context", lambda msg: ("", []))
    fu.generate_ai_response("Write a poem", mode="text", standing_instructions="\n\nSTANDING INSTRUCTIONS:\nNo emojis.")
    assert seen["system"].endswith("No emojis.")


@pytest.mark.asyncio
async def test_standing_instruction_endpoints_require_login(client):
    assert (await client.get("/user/settings/standing-instructions")).status_code in (401, 403)
    assert (await client.put("/user/settings/standing-instructions", json={"instructions": "x"})).status_code in (401, 403)
    assert (await client.post("/user/settings/fetch-training-url", json={"url": "https://example.org"})).status_code in (401, 403)


# ---------- training from a URL ----------

@pytest.fixture
def au(monkeypatch):
    import agent_module.agent_utils as au

    monkeypatch.setattr(au.socket, "getaddrinfo", lambda host, port: [(None, None, None, None, ("93.184.216.34", 0))])
    return au


def test_fetch_rejects_bad_and_private_addresses(au, monkeypatch):
    with pytest.raises(ValueError, match="valid web address"):
        au.fetch_training_page("not a url")
    monkeypatch.setattr(au.socket, "getaddrinfo", lambda host, port: [(None, None, None, None, ("127.0.0.1", 0))])
    with pytest.raises(ValueError, match="public web pages"):
        au.fetch_training_page("http://localhost/admin")
    monkeypatch.setattr(au.socket, "getaddrinfo", lambda host, port: [(None, None, None, None, ("10.0.0.5", 0))])
    with pytest.raises(ValueError, match="public web pages"):
        au.fetch_training_page("https://intranet.example.com/page")


def test_fetch_returns_text_title_and_source(au, monkeypatch):
    monkeypatch.setattr(au, "_fetch_public_html", lambda url: "<html></html>")
    monkeypatch.setattr(au, "scrape_page", lambda url, html=None: {"title": " Fall Issue ", "content": "Concrete news. " * 30})
    page = au.fetch_training_page("https://lot21.org/archive/fall-2025")
    assert page["title"] == "Fall Issue"
    assert page["source_url"] == "https://lot21.org/archive/fall-2025"
    assert page["content"].startswith("Concrete news.")


def test_fetch_explains_blocked_and_empty_pages(au, monkeypatch):
    def forbidden(url):
        raise requests.HTTPError(response=types.SimpleNamespace(status_code=403))

    monkeypatch.setattr(au, "_fetch_public_html", forbidden)
    with pytest.raises(ValueError, match="HTTP 403"):
        au.fetch_training_page("https://example.org/paywalled")
    monkeypatch.setattr(au, "_fetch_public_html", lambda url: "<html></html>")
    monkeypatch.setattr(au, "scrape_page", lambda url, html=None: {"title": "", "content": "Loading..."})
    with pytest.raises(ValueError, match="No readable text"):
        au.fetch_training_page("https://example.org/app")


class FakeResponse:
    def __init__(self, peer="93.184.216.34", location=None, text="<html>page</html>"):
        sock = types.SimpleNamespace(getpeername=lambda: (peer, 443))
        self.raw = types.SimpleNamespace(connection=types.SimpleNamespace(sock=sock))
        self.is_redirect = location is not None
        self.headers = {"location": location} if location else {}
        self.text = text

    def raise_for_status(self):
        pass

    def close(self):
        pass


def _resolve(mapping):
    return lambda host, port: [(None, None, None, None, (mapping[host], 0))]


def test_redirect_to_an_internal_address_is_refused(au, monkeypatch):
    monkeypatch.setattr(au.socket, "getaddrinfo", _resolve({"example.org": "93.184.216.34", "intranet.local": "10.0.0.5"}))
    monkeypatch.setattr(au.requests, "get", lambda url, **kw: FakeResponse(location="http://intranet.local/admin"))
    with pytest.raises(ValueError, match="public web pages"):
        au.fetch_training_page("https://example.org/moved")


def test_public_redirect_is_followed(au, monkeypatch):
    pages = {"https://example.org/a": FakeResponse(location="/a/"), "https://example.org/a/": FakeResponse(text="final")}
    monkeypatch.setattr(au.requests, "get", lambda url, **kw: pages[url])
    assert au._fetch_public_html("https://example.org/a") == "final"


def test_address_that_changes_after_the_check_is_refused(au, monkeypatch):
    # DNS said public, but the connection actually went to an internal machine
    monkeypatch.setattr(au.requests, "get", lambda url, **kw: FakeResponse(peer="127.0.0.1"))
    with pytest.raises(ValueError, match="public web pages"):
        au._fetch_public_html("https://example.org/page")


def test_loaded_page_records_its_source_url(monkeypatch):
    import agent_module.agent_utils as au

    seen = {}
    monkeypatch.setattr(au, "PostgresDB", lambda: object())
    monkeypatch.setattr(au, "create_weaviate_data_record", lambda **kw: {"id": 1, "start_time": None})
    monkeypatch.setattr(au, "load_chunks_to_weaviate", lambda **kw: {"chunks_created": 2})
    monkeypatch.setattr(au, "update_weaviate_data_success", lambda **kw: seen.update(kw))
    au.load_training_data_to_weaviate("text " * 50, "training_data", 1, "Fall issue", source_url="https://lot21.org/a")
    assert seen["extra_details"] == {"source_url": "https://lot21.org/a"}
    au.load_training_data_to_weaviate("text " * 50, "training_data", 1, "Pasted")
    assert seen["extra_details"] is None


# ---------- free-of-cost fixes ----------

@pytest.mark.parametrize(
    "prompt, mode",
    [
        ("Illustration of a coastal park with flowers", "editorial"),
        ("A field of flowers at sunset", "photo"),
        ("Wetland ecosystem at dawn", "photo"),
        ("Water flow diagram", "diagram"),
        ("A flowchart of the process", "diagram"),
        ("Aerial view of the park", "aerial"),
    ],
)
def test_image_style_matches_whole_words(prompt, mode):
    from rag_module.image_prompts import detect_visual_mode

    assert detect_visual_mode(prompt) == mode


def test_lot21_ai_attach_button_is_restored():
    html = (TEMPLATES / "content.htm").read_text()
    assert '<!-- <div style="display: none; gap: 8px;" id="imageUploadContainer">' not in html
    assert 'id="imageUploadContainer"' in html and 'id="uploadInput"' in html
    assert 'accept="image/*"' in html
    assert "syncImageUploadVisibility();" in html


def test_new_controls_are_on_their_pages():
    freeform = (TEMPLATES / "freeform.htm").read_text()
    assert 'id="outputMode"' in freeform and "mode: outputMode" in freeform
    assert 'id="projectSearch"' in freeform
    agent = (TEMPLATES / "agent.htm").read_text()
    assert 'id="standingInstructions"' in agent and 'id="trainingUrl"' in agent
    assert "source_url: fetchedSourceUrl" in agent


def test_fetched_source_is_dropped_when_text_is_replaced():
    agent = (TEMPLATES / "agent.htm").read_text()
    assert "trainingDataTextarea.addEventListener('paste'" in agent
    assert "if (!trainingDataTextarea.value.trim()) fetchedSourceUrl = '';" in agent


def test_lot21_ai_sources_are_escaped():
    html = (TEMPLATES / "content.htm").read_text()
    assert 'href="${esc(url)}"' in html and "const title = esc(" in html


# ---------- Weaviate reconnect ----------

def test_weaviate_client_reconnects_after_a_failed_start(monkeypatch):
    from service_utils.db_utils import weaviate_db as w

    db = object.__new__(w.WeaviateDB)  # skip the singleton's first connection
    attempts = []

    def connect(self):
        attempts.append(1)
        if len(attempts) == 1:
            raise w.WeaviateConnectionError("down")
        self._client, self._connection_initialized = "CLIENT", True

    monkeypatch.setattr(w.WeaviateDB, "_initialize_connection", connect)
    with pytest.raises(w.WeaviateConnectionError, match="not initialized"):
        db.client
    assert db.client == "CLIENT"  # Weaviate is back: no server restart needed
    assert db.client == "CLIENT" and len(attempts) == 2
