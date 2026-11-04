import io
import json

import pytest
from PIL import Image

from report_to_json import backends, config


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _capture(monkeypatch, reply):
    sent = []

    def fake_urlopen(req, timeout=None):
        sent.append({"url": req.full_url, "body": json.loads(req.data) if req.data else None})
        return _FakeResponse(json.dumps(reply).encode())

    monkeypatch.setattr(backends.urllib.request, "urlopen", fake_urlopen)
    return sent


def test_server_request_shape(monkeypatch):
    sent = _capture(monkeypatch, {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]})
    profile = config.get_model("qwen3-vl-4b-instruct-awq")
    backend = backends.OpenAICompatBackend(profile, "http://10.0.0.5:8000/v1/")
    gen = backend.generate("TASK: x", image=Image.new("RGB", (4, 4)), json_schema={"type": "object"})

    body = sent[0]["body"]
    assert sent[0]["url"] == "http://10.0.0.5:8000/v1/chat/completions"
    assert body["model"] == profile.repo_id
    assert body["temperature"] == 0
    content = body["messages"][0]["content"]
    assert content[0]["type"] == "image_url" and content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[1] == {"type": "text", "text": "TASK: x"}  # image before text
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert gen.text == "{}" and not gen.truncated


def test_truncation_is_reported(monkeypatch):
    _capture(monkeypatch, {"choices": [{"message": {"content": "{\"a\":"}, "finish_reason": "length"}]})
    gen = backends.OpenAICompatBackend(config.get_model("qwen3-vl-4b-instruct-awq"), "http://h/v1").generate("p")
    assert gen.truncated


def test_check_requires_the_served_model(monkeypatch):
    _capture(monkeypatch, {"data": [{"id": "something-else"}]})
    backend = backends.OpenAICompatBackend(config.get_model("qwen3-vl-4b-instruct-awq"), "http://h/v1")
    with pytest.raises(backends.BackendError, match="SERVED_NAME"):
        backend.check()


def test_unreachable_server_is_a_backend_error(monkeypatch):
    def refuse(req, timeout=None):
        raise backends.urllib.error.URLError("connection refused")
    monkeypatch.setattr(backends.urllib.request, "urlopen", refuse)
    with pytest.raises(backends.BackendError, match="Cannot reach"):
        backends.OpenAICompatBackend(config.get_model("qwen3-vl-4b-instruct-awq"), "http://h/v1").generate("p")


def test_create_backend_prefers_server_then_local_weights(monkeypatch, tmp_path):
    for var in ("R2J_MODEL_ENDPOINT", "R2J_QWEN3_VL_4B_INSTRUCT_AWQ_ENDPOINT", "R2J_QWEN3_VL_4B_INSTRUCT_AWQ_PATH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    with pytest.raises(backends.BackendError, match="not available"):
        backends.create_backend("qwen3-vl-4b-instruct-awq")

    weights = tmp_path / "Qwen3-VL-4B-Instruct-AWQ-4bit"
    weights.mkdir()
    (weights / "config.json").write_text("{}")
    (weights / "model.safetensors").write_bytes(b"")
    assert isinstance(backends.create_backend("qwen3-vl-4b-instruct-awq"), backends.TransformersBackend)

    monkeypatch.setenv("R2J_QWEN3_VL_4B_INSTRUCT_AWQ_ENDPOINT", "http://127.0.0.1:8001/v1")
    assert isinstance(backends.create_backend("qwen3-vl-4b-instruct-awq"), backends.OpenAICompatBackend)


def test_offline_mode_is_forced():
    import os
    assert os.environ["HF_HUB_OFFLINE"] == "1"


def test_the_pipeline_runs_on_exactly_one_model():
    assert list(config.MODELS) == ["qwen3-vl-4b-instruct-awq"] == [config.DEFAULT_MODEL]
    assert config.get_model(config.DEFAULT_MODEL).chat_template_kwargs == {"enable_thinking": False}
