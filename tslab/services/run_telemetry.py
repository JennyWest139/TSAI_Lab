"""Lauf-Telemetrie: Zeiten, Warnungen, Fehler, Token — fuer PDF-Laufberichte."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class ComponentTiming:
    name: str
    duration_ms: float
    started_at: datetime
    ended_at: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    models: list[str] = field(default_factory=list)

    def add(self, *, prompt: int, completion: int, total: int, model: str) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += total
        self.calls += 1
        if model and model not in self.models:
            self.models.append(model)


@dataclass
class RunTelemetry:
    run_type: str
    started_at: datetime
    output_dir: str | None = None
    browse_url: str | None = None
    components: list[ComponentTiming] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    tokens: TokenUsage = field(default_factory=TokenUsage)
    links: dict[str, str] = field(default_factory=dict)
    langfuse: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def total_ms(self) -> float:
        return sum(c.duration_ms for c in self.components)


class RunTelemetryCollector:
    """Sammelt Lauf-Metriken und schreibt optional Reports/laufbericht.pdf."""

    def __init__(self, *, run_type: str) -> None:
        self.data = RunTelemetry(run_type=run_type, started_at=datetime.now(timezone.utc))

    def warning(self, message: str) -> None:
        text = message.strip()
        if text and text not in self.data.warnings:
            self.data.warnings.append(text)

    def error(self, message: str) -> None:
        text = message.strip()
        if text and text not in self.data.errors:
            self.data.errors.append(text)

    def add_tokens(
        self,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        model: str = "",
    ) -> None:
        self.data.tokens.add(
            prompt=prompt_tokens,
            completion=completion_tokens,
            total=total_tokens or (prompt_tokens + completion_tokens),
            model=model,
        )

    def set_output(self, output_dir: str | Path, *, browse_url: str | None = None) -> None:
        from tslab.web.output_browser import browse_url_for, relative_output_path

        path = Path(output_dir).resolve()
        self.data.output_dir = str(path)
        rel = relative_output_path(path)
        self.data.browse_url = browse_url or browse_url_for(str(path))
        if rel:
            self.data.links["Output-Ordner"] = self.data.browse_url or f"/output/browse/{rel}"
        self.data.links["Absoluter Pfad"] = str(path)

    def set_langfuse_status(self, status: dict[str, Any]) -> None:
        self.data.langfuse = dict(status)

    def merge_ai_report(self, report: dict[str, Any] | None) -> None:
        if not report:
            return
        usage = report.get("token_usage") or {}
        if usage:
            self.add_tokens(
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or 0),
                model=str(usage.get("model") or ""),
            )
        for err in report.get("ai_errors") or []:
            self.error(str(err))
        for warn in report.get("ai_warnings") or []:
            self.warning(str(warn))
        if report.get("report_url"):
            self.data.links["KI-Bericht (.docx)"] = str(report["report_url"])
        if report.get("report_pdf_url"):
            self.data.links["KI-Bericht (.pdf)"] = str(report["report_pdf_url"])
        if report.get("report_rel"):
            self.data.extra["ai_report_rel"] = report["report_rel"]

    @contextmanager
    def track(self, component: str, **details: Any):
        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        try:
            yield
        except Exception as exc:
            self.error(f"{component}: {exc}")
            raise
        finally:
            ended_at = datetime.now(timezone.utc)
            ms = (time.perf_counter() - t0) * 1000
            self.data.components.append(
                ComponentTiming(
                    name=component,
                    duration_ms=ms,
                    started_at=started_at,
                    ended_at=ended_at,
                    details=dict(details),
                )
            )
            _log.info("run.%s %.1f ms %s", component, ms, details or "")

    def write_pdf(self, *, subdir: str = "Reports", basename: str = "laufbericht.pdf") -> dict[str, Any]:
        if not self.data.output_dir:
            return {"ok": False, "message": "Kein output_dir fuer Laufbericht."}
        out_dir = Path(self.data.output_dir) / subdir
        out_path = out_dir / basename
        try:
            from tslab.services.run_report_pdf import write_run_report_pdf

            with self.track("run_report_pdf"):
                write_run_report_pdf(out_path, self.data)
        except Exception as exc:
            self.error(f"PDF-Laufbericht: {exc}")
            return {"ok": False, "message": str(exc)}

        from tslab.web.output_browser import relative_output_path

        rel = relative_output_path(out_path)
        url = f"/output/file/{rel}" if rel else None
        if url:
            self.data.links["Laufbericht (PDF)"] = url
        return {
            "ok": True,
            "path": str(out_path),
            "rel": rel,
            "url": url,
            "message": f"Laufbericht: {subdir}/{basename}",
        }


def langfuse_status_from_config(config: Any) -> dict[str, Any]:
    """Prueft Langfuse-Konfiguration fuer den Laufbericht."""
    import os

    pk = (os.environ.get("LANGFUSE_PUBLIC_KEY") or getattr(config, "langfuse_public_key", None) or "").strip()
    sk = (os.environ.get("LANGFUSE_SECRET_KEY") or getattr(config, "langfuse_secret_key", None) or "").strip()
    host = (os.environ.get("LANGFUSE_HOST") or getattr(config, "langfuse_host", None) or "").strip()
    configured = bool(pk and sk)
    return {
        "configured": configured,
        "public_key_set": bool(pk),
        "secret_key_set": bool(sk),
        "host": host or "https://cloud.langfuse.com",
        "note": (
            "Traces werden an Langfuse gesendet."
            if configured
            else "Langfuse inaktiv — LANGFUSE_PUBLIC_KEY und LANGFUSE_SECRET_KEY in .env setzen."
        ),
    }
