"""Lauf-Telemetrie: Zeiten, Warnungen, Fehler, Token — fuer PDF-Laufberichte."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from tslab.services.output_paths import browse_url_for, relative_output_path

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
            label = "KI-Bericht (.docx)"
            target = report.get("target")
            if target and target != ".":
                label = f"KI-Bericht {target} (.docx)"
            self.data.links[label] = str(report["report_url"])
        if report.get("report_pdf_url"):
            label = "KI-Bericht (.pdf)"
            target = report.get("target")
            if target and target != ".":
                label = f"KI-Bericht {target} (.pdf)"
            self.data.links[label] = str(report["report_pdf_url"])
        if report.get("report_rel"):
            self.data.extra.setdefault("ai_report_rels", []).append(report["report_rel"])
        events = report.get("rate_limit_events") or []
        if events:
            self.data.extra.setdefault("rate_limit_events", []).extend(events)
        pause_count = report.get("rate_limit_pause_count")
        if pause_count is not None:
            self.data.extra["rate_limit_pause_count"] = int(
                self.data.extra.get("rate_limit_pause_count", 0)
            ) + int(pause_count)

    def merge_ai_reports(self, reports: list[dict[str, Any]] | None) -> None:
        for report in reports or []:
            self.merge_ai_report(report)
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


PENDING_BASENAME = ".pending_run.json"


def _component_to_dict(c: ComponentTiming) -> dict[str, Any]:
    return {
        "name": c.name,
        "duration_ms": c.duration_ms,
        "started_at": c.started_at.isoformat(),
        "ended_at": c.ended_at.isoformat(),
        "details": c.details,
    }


def _component_from_dict(data: dict[str, Any]) -> ComponentTiming:
    return ComponentTiming(
        name=str(data.get("name") or ""),
        duration_ms=float(data.get("duration_ms") or 0),
        started_at=datetime.fromisoformat(str(data["started_at"])),
        ended_at=datetime.fromisoformat(str(data["ended_at"])),
        details=dict(data.get("details") or {}),
    )


def save_pending_collector(collector: RunTelemetryCollector, output_dir: str | Path) -> Path:
    path = Path(output_dir).resolve() / "Reports" / PENDING_BASENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    d = collector.data
    payload = {
        "run_type": d.run_type,
        "started_at": d.started_at.isoformat(),
        "components": [_component_to_dict(c) for c in d.components],
        "warnings": list(d.warnings),
        "errors": list(d.errors),
        "tokens": asdict(d.tokens),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_pending_collector(output_dir: str | Path) -> RunTelemetryCollector | None:
    path = Path(output_dir).resolve() / "Reports" / PENDING_BASENAME
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    collector = RunTelemetryCollector(run_type=str(payload.get("run_type") or "Analyse"))
    collector.data.started_at = datetime.fromisoformat(str(payload["started_at"]))
    collector.data.components = [
        _component_from_dict(c) for c in payload.get("components") or []
    ]
    collector.data.warnings = list(payload.get("warnings") or [])
    collector.data.errors = list(payload.get("errors") or [])
    tok = payload.get("tokens") or {}
    collector.data.tokens.prompt_tokens = int(tok.get("prompt_tokens") or 0)
    collector.data.tokens.completion_tokens = int(tok.get("completion_tokens") or 0)
    collector.data.tokens.total_tokens = int(tok.get("total_tokens") or 0)
    collector.data.tokens.calls = int(tok.get("calls") or 0)
    collector.data.tokens.models = list(tok.get("models") or [])
    return collector


def clear_pending_collector(output_dir: str | Path) -> None:
    path = Path(output_dir).resolve() / "Reports" / PENDING_BASENAME
    if path.is_file():
        path.unlink()


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
