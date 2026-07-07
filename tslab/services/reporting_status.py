"""Erkennung des Berichts-/Finalisierungsstatus eines Output-Laufs."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from tslab.services.output_paths import resolve_output_dir_arg
from tslab.services.run_telemetry import PENDING_BASENAME

SESSION_BASENAME = ".report_session.json"


@dataclass(frozen=True)
class ReportingStatusInfo:
    code: str
    label: str
    badge_class: str
    detail: str = ""
    abort_available: bool = False

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "code": self.code,
            "label": self.label,
            "badge_class": self.badge_class,
            "detail": self.detail,
            "abort_available": self.abort_available,
        }


_COMPLETE = ReportingStatusInfo("complete", "fertig", "badge-ok")
_NA = ReportingStatusInfo("na", "—", "badge-muted", "Kein Output-Ordner")
_IN_PROGRESS = ReportingStatusInfo(
    "in_progress",
    "Berichte in Arbeit",
    "badge-warn",
    "KI-Berichte oder Laufbericht-Finalisierung läuft",
)
_STALLED = ReportingStatusInfo(
    "stalled",
    "Berichte hängen",
    "badge-warn",
    "Seit über 30 Minuten ohne Fortschritt",
)
_INCOMPLETE = ReportingStatusInfo(
    "incomplete",
    "Berichte unvollständig",
    "badge-incomplete",
    "Finalisierung abgebrochen — .pending_run.json liegt noch im Ordner",
)
_FAILED = ReportingStatusInfo(
    "failed",
    "KI fehlgeschlagen",
    "badge-failed",
    "KI-Berichte konnten nicht fertiggestellt werden",
)


def is_run_output_dir(path: Path) -> bool:
    """True wenn der Ordner wie ein CORR/TSA-Lauf aussieht."""
    if not path.is_dir():
        return False
    name = path.name.lower()
    if name.startswith(("tsa_", "corr_", "correlation_", "tsa-")):
        return True
    if (path / "summary.txt").is_file():
        return True
    reports = path / "Reports"
    return reports.is_dir() and (
        (reports / PENDING_BASENAME).is_file()
        or (reports / SESSION_BASENAME).is_file()
        or (reports / "laufbericht.pdf").is_file()
        or (reports / "prep_laufbericht.pdf").is_file()
    )


def _reports_dir(run_path: Path) -> Path:
    return run_path / "Reports"


def _file_age_minutes(path: Path) -> float:
    return max(0.0, (time.time() - path.stat().st_mtime) / 60.0)


def _stall_age_minutes(pending_path: Path, session_path: Path) -> float:
    if session_path.is_file():
        return _file_age_minutes(session_path)
    if pending_path.is_file():
        return _file_age_minutes(pending_path)
    return 0.0


def _load_ki_failed_detail(reports: Path) -> str:
    from tslab.services.report_runner import KI_FAILED_BASENAME

    path = reports / KI_FAILED_BASENAME
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("message") or "").strip()
    except (OSError, json.JSONDecodeError, TypeError):
        return ""


def _resolve_successful_complete(
    run_path: Path,
    reports: Path,
    *,
    pending_path: Path,
    session_path: Path,
    failed_path: Path,
    thread_active: bool,
) -> ReportingStatusInfo | None:
    """Finaler Laufbericht vorhanden und kein aktiver KI-Lauf -> fertig."""
    if not (reports / "laufbericht.pdf").is_file():
        return None
    if pending_path.is_file() or thread_active or failed_path.is_file():
        return None
    if session_path.is_file():
        try:
            from tslab.services.report_session import delete_session

            delete_session(run_path)
        except OSError:
            pass
    return _COMPLETE


def ki_abort_available(output_dir: str | Path | None) -> bool:
    return inspect_reporting_status(output_dir, reconcile=False).abort_available


def inspect_reporting_status(
    output_dir: str | Path | None,
    *,
    reconcile: bool = False,
) -> ReportingStatusInfo:
    """Status aus Dateisystem + aktivem Hintergrund-Thread ableiten."""
    del reconcile  # Abbruch nur noch manuell per abort_ki_run_by_user
    if not output_dir:
        return _NA
    try:
        run_path = resolve_output_dir_arg(output_dir)
    except (ValueError, OSError):
        return _NA
    if not run_path.is_dir():
        return _NA

    reports = _reports_dir(run_path)
    pending_path = reports / PENDING_BASENAME
    session_path = reports / SESSION_BASENAME

    try:
        from tslab.services.report_runner import KI_FAILED_BASENAME, STALE_KI_SESSION_MINUTES, ai_report_in_progress
    except ImportError:
        if session_path.is_file():
            return _IN_PROGRESS
        if pending_path.is_file():
            return _INCOMPLETE
        return _COMPLETE

    failed_path = reports / KI_FAILED_BASENAME
    thread_active = ai_report_in_progress(run_path)
    stall_age = _stall_age_minutes(pending_path, session_path)
    can_abort = (
        stall_age >= STALE_KI_SESSION_MINUTES
        and (pending_path.is_file() or session_path.is_file())
        and not failed_path.is_file()
    )

    if failed_path.is_file():
        detail = _load_ki_failed_detail(reports) or _FAILED.detail
        return ReportingStatusInfo(
            _FAILED.code,
            _FAILED.label,
            _FAILED.badge_class,
            detail,
            abort_available=False,
        )

    complete = _resolve_successful_complete(
        run_path,
        reports,
        pending_path=pending_path,
        session_path=session_path,
        failed_path=failed_path,
        thread_active=thread_active,
    )
    if complete is not None:
        return complete

    if session_path.is_file() or pending_path.is_file() or thread_active:
        if can_abort:
            detail = (
                f"Seit über {int(STALE_KI_SESSION_MINUTES)} Minuten ohne Fortschritt"
                + (" — Hintergrund-Thread läuft noch" if thread_active else "")
            )
            return ReportingStatusInfo(
                _STALLED.code,
                _STALLED.label,
                _STALLED.badge_class,
                detail,
                abort_available=True,
            )
        if thread_active or session_path.is_file():
            return _IN_PROGRESS
        return _INCOMPLETE

    return _COMPLETE
