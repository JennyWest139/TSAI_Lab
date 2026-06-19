"""LLM-Provider fuer KI-Berichte (OpenAI, spaeter Gemini)."""

from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""


@dataclass
class LLMResponse:
    text: str
    usage: LLMUsage = field(default_factory=LLMUsage)


def _env(key: str) -> str | None:
    val = os.environ.get(key, "").strip()
    return val or None


def langfuse_configured(config: Any | None = None) -> bool:
    pk = _env("LANGFUSE_PUBLIC_KEY") or (getattr(config, "langfuse_public_key", None) if config else None)
    sk = _env("LANGFUSE_SECRET_KEY") or (getattr(config, "langfuse_secret_key", None) if config else None)
    return bool(pk and sk)


def parse_model_id(model_id: str, *, default_provider: str = "openai") -> tuple[str, str]:
    """'openai:gpt-4o-mini' -> ('openai', 'gpt-4o-mini')."""
    text = (model_id or "").strip()
    if ":" in text:
        provider, name = text.split(":", 1)
        return provider.strip().lower(), name.strip()
    return default_provider, text or "gpt-4o-mini"


def _token_limit_kw(model: str, max_tokens: int) -> dict[str, int]:
    """Neuere Reasoning-Modelle verlangen max_completion_tokens."""
    name = (model or "").lower()
    if name.startswith(("o1", "o3", "o4", "gpt-5")):
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens}


def _usage_from_response(resp: Any, *, model: str) -> LLMUsage:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return LLMUsage(model=model)
    return LLMUsage(
        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        model=model,
    )


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
    ) -> LLMResponse: ...

    @abstractmethod
    def describe_image(
        self,
        *,
        image_path: Path,
        prompt: str,
        model: str,
        max_tokens: int,
        trace_name: str,
    ) -> LLMResponse: ...


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None, *, config: Any | None = None) -> None:
        self._api_key = api_key
        self._config = config
        self._use_langfuse = langfuse_configured(config)

    def _client(self):
        if not self._api_key:
            raise ValueError(
                "OPENAI_API_KEY fehlt. Bitte in .env setzen (nicht committen)."
            )
        if self._use_langfuse:
            try:
                from langfuse.openai import OpenAI  # type: ignore[import-untyped]
            except ImportError:
                from openai import OpenAI  # type: ignore[import-untyped]
        else:
            from openai import OpenAI  # type: ignore[import-untyped]
        return OpenAI(api_key=self._api_key)

    def _create_completion(self, *, model: str, messages: list, max_tokens: int, trace_name: str):
        client = self._client()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            **_token_limit_kw(model, max_tokens),
        }
        if self._use_langfuse:
            kwargs["name"] = trace_name
        return client.chat.completions.create(**kwargs)

    def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        trace_name: str,
    ) -> LLMResponse:
        resp = self._create_completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            trace_name=trace_name,
        )
        text = (resp.choices[0].message.content or "").strip()
        return LLMResponse(text=text, usage=_usage_from_response(resp, model=model))

    def describe_image(
        self,
        *,
        image_path: Path,
        prompt: str,
        model: str,
        max_tokens: int,
        trace_name: str,
    ) -> LLMResponse:
        data = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
        mime = "image/png"
        if image_path.suffix.lower() in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        resp = self._create_completion(
            model=model,
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
            max_tokens=max_tokens,
            trace_name=trace_name,
        )
        text = (resp.choices[0].message.content or "").strip()
        return LLMResponse(text=text, usage=_usage_from_response(resp, model=model))


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
    ) -> LLMResponse:
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
    ) -> LLMResponse:
        raise NotImplementedError("Gemini Vision noch nicht implementiert.")


def get_provider(provider_name: str, config: Any) -> LLMProvider:
    name = provider_name.lower()
    if name == "openai":
        key = _env("OPENAI_API_KEY") or getattr(config, "openai_api_key", None)
        return OpenAIProvider(key, config=config)
    if name == "gemini":
        key = _env("GEMINI_API_KEY") or getattr(config, "gemini_api_key", None)
        return GeminiProvider(key)
    raise ValueError(f"Unbekannter AI-Provider: {provider_name!r}")


def init_langfuse(config: Any) -> bool:
    """LangFuse-Umgebung setzen (optional). Gibt True zurueck wenn konfiguriert."""
    pk = _env("LANGFUSE_PUBLIC_KEY") or getattr(config, "langfuse_public_key", None)
    sk = _env("LANGFUSE_SECRET_KEY") or getattr(config, "langfuse_secret_key", None)
    host = _env("LANGFUSE_HOST") or getattr(config, "langfuse_host", None)
    if pk:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", pk)
    if sk:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", sk)
    if host:
        os.environ.setdefault("LANGFUSE_HOST", host)
    return bool(pk and sk)


def flush_langfuse() -> None:
    """Offene Langfuse-Traces senden (best effort)."""
    try:
        from langfuse import Langfuse  # type: ignore[import-untyped]

        Langfuse().flush()
    except Exception:
        pass
