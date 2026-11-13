"""Provider-neutral LLM access (OpenRouter by default, any OpenAI-compatible server works).

Configure in backend/.env:

  CHROMASWARM_LLM_BASE_URL      https://openrouter.ai/api/v1  (or DashScope, Ollama, vLLM...)
  CHROMASWARM_LLM_API_KEY       provider key
  CHROMASWARM_LLM_MODEL         text role: B1-B7 interpretation, B7 feedback, B5 prose
                                (unset -> rule-based baseline, no LLM at all)
  CHROMASWARM_LLM_MODEL_CODE    code role: B9 copy / codegen         (default: text model)
  CHROMASWARM_LLM_MODEL_VISION  vision role: Clone mode from images (default: text model)
  CHROMASWARM_LLM_EXTRA_BODY    optional JSON merged into every request (overrides the defaults)
  CHROMASWARM_LLM_TIMEOUT       seconds, default 60

On OpenRouter the model catalogue (public /models endpoint) is read once so each
model gets the right request: reasoning switched off where the model allows it
(or set to its lowest effort where reasoning is mandatory), JSON mode only where
it is supported, and image input checked for the vision role.

The LLM only *interprets* or *writes prose*; every gate, score and design number
stays in deterministic code (CLAUDE.md decisions 2 and 7).
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.request
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any, Protocol

ROLES = ("text", "code", "vision")
EFFORT_ORDER = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
OPENROUTER_HEADERS = {"HTTP-Referer": "https://github.com/Chuki1234/ChromaSwarm", "X-OpenRouter-Title": "ChromaSwarm"}


class LLMError(RuntimeError):
    pass


def is_openrouter(base_url: str | None) -> bool:
    return bool(base_url) and "openrouter.ai" in base_url


@dataclass(frozen=True)
class LLMConfig:
    model: str  # the model of the role this config is for (text by default)
    base_url: str | None = None
    api_key: str = "not-needed"
    extra_body: dict[str, Any] = field(default_factory=dict)  # user override, wins over defaults
    timeout: float = 60.0
    models: dict[str, str] = field(default_factory=dict)  # role -> model id

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
        models = {"text": model,
                  "code": env.get("CHROMASWARM_LLM_MODEL_CODE", "").strip() or model,
                  "vision": env.get("CHROMASWARM_LLM_MODEL_VISION", "").strip() or model}
        return cls(model=model, base_url=env.get("CHROMASWARM_LLM_BASE_URL") or None,
                   api_key=env.get("CHROMASWARM_LLM_API_KEY") or "not-needed", extra_body=extra_body,
                   timeout=float(env.get("CHROMASWARM_LLM_TIMEOUT", "60")), models=models)

    def for_role(self, role: str) -> LLMConfig:
        if role not in ROLES:
            raise LLMError(f"unknown role {role!r}")
        return replace(self, model=self.models.get(role, self.model))


# ------------------------------------------------------------------ OpenRouter catalogue

@lru_cache(maxsize=4)
def openrouter_catalogue(base_url: str) -> dict[str, dict]:
    """Public model list (no key needed). Empty dict when unreachable: requests then use safe defaults."""
    try:
        import certifi  # python.org builds on macOS ship without a CA bundle for urllib

        ctx = ssl.create_default_context(cafile=certifi.where())
        req = urllib.request.Request(base_url.rstrip("/") + "/models", headers={"User-Agent": "ChromaSwarm"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return {m["id"]: m for m in json.load(r).get("data", [])}
    except Exception:
        return {}


def reasoning_setting(meta: dict | None) -> dict | None:
    """Short classification calls do not need reasoning: off where allowed, lowest effort where mandatory."""
    if not meta or "reasoning" not in meta.get("supported_parameters", []):
        return None
    info = meta.get("reasoning") or {}
    if not info.get("mandatory"):
        return {"effort": "none"}
    efforts = [e for e in EFFORT_ORDER if e in (info.get("supported_efforts") or [])]
    return {"effort": efforts[0]} if efforts else None


def supports(meta: dict | None, param: str) -> bool:
    return meta is None or param in meta.get("supported_parameters", [])  # unknown model: try it


def accepts_images(meta: dict | None) -> bool:
    return bool(meta) and "image" in meta.get("architecture", {}).get("input_modalities", [])


# ------------------------------------------------------------------ chat

class JSONChat(Protocol):
    """One system + user turn in (optionally with images), one JSON object out."""

    model: str

    def complete_json(self, system: str, user: str, images: list[str] | None = None) -> dict[str, Any]: ...


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


def _mentions_json_mode(error: Exception) -> bool:
    text = str(error).lower()
    return "response_format" in text or "json_object" in text or "json mode" in text


class OpenAICompatChat:
    def __init__(self, cfg: LLMConfig, client: Any = None, catalogue: dict[str, dict] | None = None):
        self.model = cfg.model
        self._cfg = cfg
        if catalogue is None:
            catalogue = openrouter_catalogue(cfg.base_url) if is_openrouter(cfg.base_url) else {}
        self.meta: dict | None = catalogue.get(cfg.model) if catalogue else None
        self._json_mode = supports(self.meta, "response_format")
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=cfg.timeout, max_retries=1,
                            default_headers=OPENROUTER_HEADERS if is_openrouter(cfg.base_url) else None)
        self._client = client

    def _extra_body(self) -> dict | None:
        body: dict[str, Any] = {}
        if is_openrouter(self._cfg.base_url) and (r := reasoning_setting(self.meta)):
            body["reasoning"] = r
        body.update(self._cfg.extra_body)  # the user's explicit setting always wins
        return body or None

    def _messages(self, system: str, user: str, images: list[str] | None) -> list[dict]:
        if not images:
            return [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if self.meta is not None and not accepts_images(self.meta):
            raise LLMError(f"{self.model} does not accept image input; set CHROMASWARM_LLM_MODEL_VISION")
        parts = [{"type": "text", "text": user}] + [{"type": "image_url", "image_url": {"url": u}} for u in images]
        return [{"role": "system", "content": system}, {"role": "user", "content": parts}]

    def complete_json(self, system: str, user: str, images: list[str] | None = None) -> dict[str, Any]:
        messages = self._messages(system, user, images)
        resp = None
        for attempt in (1, 2):
            kwargs: dict[str, Any] = dict(model=self.model, messages=messages, temperature=0, max_tokens=1500,
                                          extra_body=self._extra_body())
            if self._json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                resp = self._client.chat.completions.create(**kwargs)
                break
            except Exception as e:  # network, auth, unknown model...
                if attempt == 1 and self._json_mode and _mentions_json_mode(e):
                    self._json_mode = False  # this model has no JSON mode: ask in the prompt instead
                    continue
                raise LLMError(f"{type(e).__name__}: {e}") from e
        if resp is None or not resp.choices:
            raise LLMError("empty response")
        choice = resp.choices[0]
        content = choice.message.content or ""
        if not content.strip() and getattr(choice, "finish_reason", None) == "length":
            raise LLMError("output budget used up by reasoning before any answer (raise max_tokens or lower effort)")
        return parse_json_object(content)


def main() -> int:
    """`uv run python -m chromaswarm.agents.llm`: check the configured models end to end."""
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    cfg = LLMConfig.from_env()
    if cfg is None:
        print("Chưa cấu hình: điền CHROMASWARM_LLM_MODEL và CHROMASWARM_LLM_API_KEY trong backend/.env")
        return 1
    print(f"Endpoint: {cfg.base_url or 'mặc định'}")
    catalogue = openrouter_catalogue(cfg.base_url) if is_openrouter(cfg.base_url) else {}
    ok = True
    for role in ROLES:
        mid = cfg.models[role]
        meta = catalogue.get(mid)
        if catalogue and meta is None:
            print(f"  {role:6} {mid}: KHÔNG có trên OpenRouter — kiểm tra lại ID tại openrouter.ai/models")
            ok = False
            continue
        if meta:
            p = meta.get("pricing", {})
            price = f"${float(p.get('prompt', 0)) * 1e6:.2f} / ${float(p.get('completion', 0)) * 1e6:.2f} mỗi 1M token"
            notes = [price, "đọc ảnh" if accepts_images(meta) else "không đọc ảnh",
                     f"reasoning={reasoning_setting(meta)}" if reasoning_setting(meta) else "không có reasoning"]
            if role == "vision" and not accepts_images(meta):
                notes.append("CẦN model đọc được ảnh cho Clone mode")
                ok = False
            print(f"  {role:6} {mid}: " + " · ".join(notes))
        else:
            print(f"  {role:6} {mid}")
    if not ok:
        return 1
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
