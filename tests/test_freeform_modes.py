"""Free Form AI output selector: Text / Image / Text & Image."""
import base64
import types

import pytest

IMG = {"name": "ref.png", "type": "image/png", "data": base64.b64encode(b"png-bytes").decode()}
PREVIOUS_IMAGE = [
    {"role": "USER", "content": "a park", "content_type": "TEXT"},
    {"role": "ASSISTANT", "content": "data:image/png;base64," + base64.b64encode(b"old").decode(), "content_type": "IMAGE"},
]


@pytest.fixture
def ff(monkeypatch):
    import freeform_module.freeform_utils as fu

    calls = {"generate": [], "edit": [], "text": []}

    def fake_text(content, generation_config, system_instruction=None):
        calls["text"].append(content)
        return types.SimpleNamespace(text="Some text.")

    monkeypatch.setattr(fu, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(fu, "image_client", object(), raising=False)
    monkeypatch.setattr(fu, "generate_with_model_fallback", fake_text)
    monkeypatch.setattr(fu, "fetch_web_context", lambda msg: ("", []))
    monkeypatch.setattr(fu, "generate_image", lambda prompt, ctx: calls["generate"].append(prompt) or "NEWIMG")
    monkeypatch.setattr(fu, "edit_image", lambda prompt, data, mime: calls["edit"].append(data) or "EDITED")
    return fu, calls


def test_text_mode_never_makes_an_image(ff):
    fu, calls = ff
    text, image, kind = fu.generate_ai_response("Create an image of a park", mode="text")
    assert (image, kind) == (None, "TEXT") and text == "Some text."
    assert not calls["generate"] and not calls["edit"]


def test_text_mode_analyses_an_attached_image_instead_of_editing(ff):
    fu, calls = ff
    _, image, kind = fu.generate_ai_response("Edit this image please", attachments=[IMG], mode="text")
    assert (image, kind) == (None, "TEXT") and not calls["edit"]


def test_image_mode_generates_without_trigger_words(ff):
    fu, calls = ff
    text, image, kind = fu.generate_ai_response("A coastal park at dusk", mode="image")
    assert (text, image, kind) == ("", "NEWIMG", "IMAGE")
    assert calls["generate"] and not calls["text"]


def test_text_and_image_mode_returns_both(ff):
    fu, calls = ff
    text, image, kind = fu.generate_ai_response("A coastal park at dusk", mode="text_and_image")
    assert (text, image, kind) == ("Some text.", "NEWIMG", "MULTIMODAL")


def test_image_mode_uses_attached_image_as_starting_point(ff):
    fu, calls = ff
    _, image, kind = fu.generate_ai_response("In this style, show a wetland", attachments=[IMG], mode="image")
    assert (image, kind) == ("EDITED", "IMAGE")
    assert calls["edit"] == [b"png-bytes"] and not calls["generate"]


def test_text_and_image_mode_with_attachment_returns_both(ff):
    fu, calls = ff
    text, image, kind = fu.generate_ai_response("In this style, show a wetland", attachments=[IMG], mode="text_and_image")
    assert (text, image, kind) == ("Some text.", "EDITED", "MULTIMODAL")


def test_image_mode_edit_request_reworks_previous_image(ff):
    fu, calls = ff
    _, image, kind = fu.generate_ai_response("Make it brighter", chat_history=PREVIOUS_IMAGE, mode="image")
    assert (image, kind) == ("EDITED", "IMAGE")
    assert calls["edit"] == [b"old"] and not calls["generate"]


def test_no_mode_keeps_wording_detection(ff):
    fu, calls = ff
    _, image, kind = fu.generate_ai_response("Create an image of a park")
    assert (image, kind) == ("NEWIMG", "IMAGE")
    _, image, kind = fu.generate_ai_response("Write a poem about a park")
    assert (image, kind) == (None, "TEXT")


def test_chat_request_accepts_only_known_modes():
    from pydantic import ValidationError

    from freeform_module.freeform_responses import ChatCompletionRequest

    assert ChatCompletionRequest(project_id=1, message="hi", mode="image").mode == "image"
    assert ChatCompletionRequest(project_id=1, message="hi").mode is None
    with pytest.raises(ValidationError):
        ChatCompletionRequest(project_id=1, message="hi", mode="video")


def test_image_mode_long_message_still_returns_an_image(ff):
    fu, calls = ff
    long_prompt = "Make it brighter and use this brief: " + "coastal park details " * 60
    _, image, kind = fu.generate_ai_response(long_prompt, chat_history=PREVIOUS_IMAGE, mode="image")
    assert kind == "IMAGE" and image in ("NEWIMG", "EDITED")


def test_text_beside_edited_attachment_is_based_on_the_images(ff, monkeypatch):
    # FO-11: the text step only saw the chat, so it described earlier documents
    fu, calls = ff
    edited = "data:image/png;base64," + base64.b64encode(b"night").decode()
    monkeypatch.setattr(fu, "edit_image", lambda prompt, data, mime: edited)
    history = [{"role": "ASSISTANT", "content": "Summary of the Manhattan PDF", "content_type": "TEXT"}]
    text, image, kind = fu.generate_ai_response(
        "Turn this into a night scene and describe the changes", chat_history=history, attachments=[IMG], mode="text_and_image"
    )
    assert (image, kind) == (edited, "MULTIMODAL")
    sent = calls["text"][-1]
    assert isinstance(sent, list)
    assert {"mime_type": "image/png", "data": b"png-bytes"} in sent
    assert {"mime_type": "image/png", "data": b"night"} in sent


def test_text_and_image_download_includes_the_image(monkeypatch):
    # RG-07: the image of a Text & Image answer lives in attachments and was left out
    from download_module import download_utils as du

    img = "data:image/png;base64," + base64.b64encode(b"night").decode()
    tables = {
        "freeform_chat": [{"id": 9, "project_id": 1, "content": "Here are the changes.", "attachments": img, "created_on": None}],
        "freeform_projects": [{"project_name": "QA"}],
    }

    class FakeDB:
        def read(self, table, **kw):
            return tables[table]

    monkeypatch.setattr(du, "PostgresDB", FakeDB)
    item = du.get_freeform_message_item(9)
    assert item["body"] == "Here are the changes."
    assert item["images"] == [img]
