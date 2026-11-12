"""Provider-neutral LLM access for the B1-B4 consultant.

Any server that speaks the OpenAI Chat Completions API works: Alibaba Cloud
DashScope (Qwen), OpenRouter, Ollama, LM Studio, vLLM. Configure with env vars:

  CHROMASWARM_LLM_MODEL      e.g. qwen3.8-flash            (unset -> rule-based baseline)
  CHROMASWARM_LLM_BASE_URL   e.g. https://dashscope-intl.aliyuncs.com/compatible-mode/v1
  CHROMASWARM_LLM_API_KEY    provider key (any non-empty string for local servers)
  CHROMASWARM_LLM_EXTRA_BODY optional JSON merged into each request,
                             e.g. {"enable_thinking": false} for Qwen3 on DashScope
  CHROMASWARM_LLM_TIMEOUT    seconds, default 30

The LLM only *interprets* text into a closed set of values; every gate, score
and design number stays in deterministic code (CLAUDE.md decisions 2 and 7).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    model: str
    base_url: str | None = None
    api_key: str = "not-needed"
    extra_body: dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> LLMConfig | None:
        env = dict(os.environ if env is None else env)
        model = env.get("CHROMASWARM_LLM_MODEL", "").strip()
        if not model:
            return None
        if "your-" in env.get("CHROMASWARM_LLM_API_KEY", ""):
            return None  # .env copied but the placeholder key not replaced yet
        extra = env.get("CHROMASWARM_LLM_EXTRA_BODY", "").strip()
        try:
            extra_body = json.loads(extra) if extra else {}
        except json.JSONDecodeError as e:
            raise LLMError(f"CHROMASWARM_LLM_EXTRA_BODY is not valid JSON: {e}") from e
        return cls(
            model=model,
            base_url=env.get("CHROMASWARM_LLM_BASE_URL") or None,
            api_key=env.get("CHROMASWARM_LLM_API_KEY") or "not-needed",
            extra_body=extra_body,
            timeout=float(env.get("CHROMASWARM_LLM_TIMEOUT", "30")),
        )


class JSONChat(Protocol):
    """One system + user turn in, one JSON object out."""

    model: str

    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...


_THINK = re.compile(r"<think>.*?</think>", re.S)
_OBJECT = re.compile(r"\{.*\}", re.S)


def parse_json_object(text: str) -> dict[str, Any]:
    """Tolerates reasoning tags and ```json fences some open models emit."""
    text = _THINK.sub("", text or "").strip()
    m = _OBJECT.search(text)
    if not m:
        raise LLMError(f"no JSON object in model output: {text[:200]!r}")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LLMError(f"invalid JSON from model: {e}") from e
    if not isinstance(data, dict):
        raise LLMError("model output is not a JSON object")
    return data


class OpenAICompatChat:
    def __init__(self, cfg: LLMConfig):
        from openai import OpenAI

        self.model = cfg.model
        self._cfg = cfg
        self._client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=cfg.timeout, max_retries=1)

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=400,
                extra_body=self._cfg.extra_body or None,
            )
        except Exception as e:  # network, auth, unknown model...
            raise LLMError(f"{type(e).__name__}: {e}") from e
        if not resp.choices:
            raise LLMError("empty response")
        return parse_json_object(resp.choices[0].message.content or "")


def main() -> int:
    """`uv run python -m chromaswarm.agents.llm`: check the configured model end to end."""
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    cfg = LLMConfig.from_env()
    if cfg is None:
        print("Chưa cấu hình: điền CHROMASWARM_LLM_MODEL và CHROMASWARM_LLM_API_KEY trong backend/.env")
        return 1
    print(f"Model: {cfg.model}\nEndpoint: {cfg.base_url or 'mặc định'}")
    from chromaswarm.agents.llm_consultant import LLMConsultant

    chat = OpenAICompatChat(cfg)
    try:
        chat.complete_json('Trả về JSON {"ok": true}.', "ping")
    except LLMError as e:
        print(f"LỖI kết nối: {e}")
        return 1
    c = LLMConsultant(chat)
    samples = [("theme", "nhìn phải ra chất công nghệ, gọn gàng"), ("theme", "đẹp là được"),
               ("color", "giấy kem ấm, màu xanh rêu"), ("margins", "để mọi thứ thoáng thoáng chút"),
               ("scope", "Dân văn phòng 25-35, dùng điện thoại, muốn họ bấm Đăng ký dùng thử")]
    for pillar, text in samples:
        print(f"  {pillar:8} {text!r:72} -> {c.interpret(pillar, text)}")
    print("OK: backend sẽ dùng model này sau khi khởi động lại.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
