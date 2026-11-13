"""OpenRouter wiring: per-role models, per-model request shaping, JSON-mode fallback. No network."""

from types import SimpleNamespace

import pytest

from chromaswarm.agents.llm import LLMConfig, LLMError, OpenAICompatChat, reasoning_setting

OR = "https://openrouter.ai/api/v1"
CATALOGUE = {
    "qwen/qwen3.8-flash": {"supported_parameters": ["reasoning", "response_format", "max_tokens"],
                           "reasoning": {"mandatory": False, "default_enabled": True},
                           "architecture": {"input_modalities": ["text", "image"]}},
    "anthropic/claude-sonnet-5.5": {"supported_parameters": ["reasoning", "response_format"],
                                    "reasoning": {"mandatory": True, "supported_efforts": ["max", "high", "low"]},
                                    "architecture": {"input_modalities": ["text", "image"]}},
    "qwen/qwen3-coder-next": {"supported_parameters": ["max_tokens"], "architecture": {"input_modalities": ["text"]}},
}


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        content, finish = reply if isinstance(reply, tuple) else (reply, "stop")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)])


def cfg(model, **env):
    return LLMConfig.from_env({"CHROMASWARM_LLM_MODEL": model, "CHROMASWARM_LLM_BASE_URL": OR,
                               "CHROMASWARM_LLM_API_KEY": "sk-or-test", **env})


def test_roles_default_to_the_text_model_and_can_be_split():
    c = cfg("qwen/qwen3.8-flash")
    assert c.models == {"text": "qwen/qwen3.8-flash", "code": "qwen/qwen3.8-flash", "vision": "qwen/qwen3.8-flash"}
    c = cfg("qwen/qwen3.8-flash", CHROMASWARM_LLM_MODEL_CODE="qwen/qwen3-coder-next")
    assert c.for_role("code").model == "qwen/qwen3-coder-next" and c.for_role("text").model == "qwen/qwen3.8-flash"
    with pytest.raises(LLMError):
        c.for_role("audio")


def test_reasoning_is_off_where_allowed_and_lowest_where_mandatory():
    assert reasoning_setting(CATALOGUE["qwen/qwen3.8-flash"]) == {"effort": "none"}
    assert reasoning_setting(CATALOGUE["anthropic/claude-sonnet-5.5"]) == {"effort": "low"}
    assert reasoning_setting(CATALOGUE["qwen/qwen3-coder-next"]) is None
    assert reasoning_setting(None) is None


def test_request_shape_follows_the_catalogue():
    client = FakeClient(['{"ok": true}'])
    chat = OpenAICompatChat(cfg("qwen/qwen3.8-flash"), client=client, catalogue=CATALOGUE)
    assert chat.complete_json("s", "u") == {"ok": True}
    sent = client.calls[0]
    assert sent["extra_body"] == {"reasoning": {"effort": "none"}} and sent["response_format"] == {"type": "json_object"}

    client = FakeClient(['{"ok": true}'])
    OpenAICompatChat(cfg("qwen/qwen3-coder-next"), client=client, catalogue=CATALOGUE).complete_json("s", "u")
    assert "response_format" not in client.calls[0] and client.calls[0]["extra_body"] is None


def test_user_extra_body_wins():
    client = FakeClient(['{"ok": 1}'])
    c = cfg("qwen/qwen3.8-flash", CHROMASWARM_LLM_EXTRA_BODY='{"reasoning": {"effort": "low"}}')
    OpenAICompatChat(c, client=client, catalogue=CATALOGUE).complete_json("s", "u")
    assert client.calls[0]["extra_body"] == {"reasoning": {"effort": "low"}}


def test_json_mode_rejected_is_retried_without_it():
    client = FakeClient([RuntimeError("400: response_format json_object is not supported"), '{"value": "airy"}'])
    chat = OpenAICompatChat(cfg("some/unknown-model"), client=client, catalogue={})
    assert chat.complete_json("s", "u") == {"value": "airy"}
    assert "response_format" in client.calls[0] and "response_format" not in client.calls[1]


def test_reasoning_eating_the_budget_is_reported():
    client = FakeClient([("", "length")])
    with pytest.raises(LLMError, match="reasoning"):
        OpenAICompatChat(cfg("qwen/qwen3.8-flash"), client=client, catalogue=CATALOGUE).complete_json("s", "u")


def test_images_need_a_vision_model():
    client = FakeClient(['{"ok": true}'])
    chat = OpenAICompatChat(cfg("qwen/qwen3.8-flash"), client=client, catalogue=CATALOGUE)
    chat.complete_json("s", "u", images=["data:image/png;base64,AAAA"])
    parts = client.calls[0]["messages"][1]["content"]
    assert parts[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    with pytest.raises(LLMError, match="image"):
        OpenAICompatChat(cfg("qwen/qwen3-coder-next"), client=FakeClient([]), catalogue=CATALOGUE).complete_json(
            "s", "u", images=["data:image/png;base64,AAAA"])
