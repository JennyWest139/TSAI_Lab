"""LLM-Provider fuer KI-Berichte (OpenAI, spaeter Gemini)."""

from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider: str
    label: str
    model_name: str
    vision: bool = True
    enabled: bool = True


def _env(key: str) -> str | None:
    val = os.environ.get(key, "").strip()
    return val or None


def parse_model_id(model_id: str, *, default_provider: str = "openai") -> tuple[str, str]:
    """'openai:gpt-4o-mini' -> ('openai', 'gpt-4o-mini')."""
    text = (model_id or "").strip()
    if ":" in text:
        provider, name = text.split(":", 1)
        return provider.strip().lower(), name.strip()
    return default_provider, text or "gpt-4o-mini"


class LLMProvider(ABC):
    @abstractmethod
    def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        trace_name: str,
    ) -> str: ...

    @abstractmethod
    def describe_image(
        self,
        *,
        image_path: Path,
        prompt: str,
        model: str,
        max_tokens: int,
        trace_name: str,
    ) -> str: ...


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    def _client(self):
        if not self._api_key:
            raise ValueError(
                "OPENAI_API_KEY fehlt. Bitte in .env setzen (nicht committen)."
            )
        try:
            from langfuse.openai import OpenAI  # type: ignore[import-untyped]
        except ImportError:
            from openai import OpenAI  # type: ignore[import-untyped]
        return OpenAI(api_key=self._api_key)

    def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        trace_name: str,
    ) -> str:
        client = self._client()
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            name=trace_name,
        )
        return (resp.choices[0].message.content or "").strip()

    def describe_image(
        self,
        *,
        image_path: Path,
        prompt: str,
        model: str,
        max_tokens: int,
        trace_name: str,
    ) -> str:
        data = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
        mime = "image/png"
        if image_path.suffix.lower() in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        client = self._client()
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{data}"},
                        },
                    ],
                }
            ],
            name=trace_name,
        )
        return (resp.choices[0].message.content or "").strip()


class GeminiProvider(LLMProvider):
    """Platzhalter — aktiviert wenn GEMINI_API_KEY gesetzt und google-genai installiert."""

    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        trace_name: str,
    ) -> str:
        raise NotImplementedError(
            "Gemini-Provider ist vorbereitet aber noch nicht implementiert. "
            "GEMINI_API_KEY setzen und google-genai nachruesten."
        )

    def describe_image(
        self,
        *,
        image_path: Path,
        prompt: str,
        model: str,
        max_tokens: int,
        trace_name: str,
    ) -> str:
        raise NotImplementedError("Gemini Vision noch nicht implementiert.")


def get_provider(provider_name: str, config: Any) -> LLMProvider:
    name = provider_name.lower()
    if name == "openai":
        key = _env("OPENAI_API_KEY") or getattr(config, "openai_api_key", None)
        return OpenAIProvider(key)
    if name == "gemini":
        key = _env("GEMINI_API_KEY") or getattr(config, "gemini_api_key", None)
        return GeminiProvider(key)
    raise ValueError(f"Unbekannter AI-Provider: {provider_name!r}")


def init_langfuse(config: Any) -> None:
    """LangFuse-Umgebung setzen (optional)."""
    pk = _env("LANGFUSE_PUBLIC_KEY") or getattr(config, "langfuse_public_key", None)
    sk = _env("LANGFUSE_SECRET_KEY") or getattr(config, "langfuse_secret_key", None)
    host = _env("LANGFUSE_HOST") or getattr(config, "langfuse_host", None)
    if pk:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", pk)
    if sk:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", sk)
    if host:
        os.environ.setdefault("LANGFUSE_HOST", host)
