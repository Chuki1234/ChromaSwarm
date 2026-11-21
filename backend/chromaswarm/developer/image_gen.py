"""Last resort for photos (§1.3: never grey boxes): images generated for the brief by an image model.

Used only when the photo bot found nothing fitting and there are no curated photos for the topic,
and only when `CHROMASWARM_IMAGE_MODEL` names an image model (e.g. an OpenRouter model with image
output). Generated images are saved like uploads (`uploads/generated-….png`), copied into the app
at B9 and labelled as AI-generated in content/images.ts — never passed off as real photographs of
the user's product. Prompts ask for no text, no logos and no real people's likeness.
"""

from __future__ import annotations

import base64
import logging
import os
import re

import httpx

log = logging.getLogger(__name__)

PROMPT = ("Editorial photograph for a website about: {brief}. Subject: {subject}. Natural light, calm composition, "
          "generous negative space, realistic, professional photography, {ratio}. No text, no letters, no logos, "
          "no watermarks, no recognisable real people.")
DATA_URI = re.compile(r"^data:image/(png|jpeg|webp);base64,(.+)$", re.S)


class ImageGenerator:
    """(brief, subjects) -> list of image bytes. Never raises."""

    def __init__(self, model: str, base_url: str, api_key: str, timeout: float = 120, client: httpx.Client | None = None):
        self.model, self.base_url, self.api_key, self.timeout = model, base_url.rstrip("/"), api_key, timeout
        self.client = client

    def one(self, prompt: str) -> bytes | None:
        body = {"model": self.model, "modalities": ["image", "text"],
                "messages": [{"role": "user", "content": prompt}]}
        try:
            client = self.client or httpx.Client(timeout=self.timeout)
            r = client.post(f"{self.base_url}/chat/completions", json=body,
                            headers={"Authorization": f"Bearer {self.api_key}"})
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            for img in msg.get("images") or []:
                url = (img.get("image_url") or {}).get("url", "")
                if m := DATA_URI.match(url):
                    return base64.b64decode(m.group(2))
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            log.warning("image generation failed: %s", e)
        return None

    def __call__(self, brief: str, subjects: list[str], wide_first: bool = True) -> list[bytes]:
        out = []
        for i, subject in enumerate(subjects):
            ratio = "wide 16:9 frame" if i == 0 and wide_first else "4:5 portrait frame"
            if data := self.one(PROMPT.format(brief=brief[:300], subject=subject[:120], ratio=ratio)):
                out.append(data)
        return out


def build_image_generator(env: dict[str, str] | None = None) -> ImageGenerator | None:
    values = dict(os.environ if env is None else env)
    model = values.get("CHROMASWARM_IMAGE_MODEL", "").strip()
    if not model:
        return None
    from chromaswarm.agents.llm import LLMConfig
    cfg = LLMConfig.from_env(values)
    if cfg is None or not cfg.base_url:
        return None
    return ImageGenerator(model, cfg.base_url, cfg.api_key)
