"""KI-Berichte (Phase 6 — Architektur-Vorbereitung).

Integration mit OpenAI + LangFuse fuer nachgelagerte Berichtsgenerierung.
Vollstaendige Implementierung in separatem PR geplant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tslab.config_loader import load_defaults


@dataclass(frozen=True)
class ReportConfig:
    enabled: bool
    openai_api_key: str | None
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_host: str | None
    model: str


def load_report_config() -> ReportConfig:
    cfg = load_defaults().get("ai_reports", {})
    return ReportConfig(
        enabled=bool(cfg.get("enabled")),
        openai_api_key=cfg.get("openai_api_key") or None,
        langfuse_public_key=cfg.get("langfuse_public_key") or None,
        langfuse_secret_key=cfg.get("langfuse_secret_key") or None,
        langfuse_host=cfg.get("langfuse_host") or "https://cloud.langfuse.com",
        model=str(cfg.get("model", "gpt-4o-mini")),
    )


def generate_object_report(
    entity_type: str,
    entity_id: str | int,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stub — wirft NotImplementedError bis OpenAI/LangFuse aktiviert sind."""
    config = load_report_config()
    if not config.enabled:
        return {
            "ok": False,
            "status": "disabled",
            "message": "AI-Berichte sind in config/defaults.yaml deaktiviert (ai_reports.enabled).",
        }
    raise NotImplementedError(
        "AI-Berichtsgenerierung ist vorbereitet aber noch nicht implementiert. "
        "Aktivieren Sie ai_reports.enabled und installieren Sie openai + langfuse."
    )
