"""Erkennung des Berichts-/Finalisierungsstatus eines Output-Laufs."""

from __future__ import annotations

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

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "label": self.label,
            "badge_class": self.badge_class,
            "detail": self.detail,
        }


_COMPLETE = ReportingStatusInfo("complete", "fertig", "badge-ok")
_NA = ReportingStatusInfo("na", "—", "badge-muted", "Kein Output-Ordner")
_IN_PROGRESS = ReportingStatusInfo(
    "in_progress",
    "Berichte in Arbeit",
    "badge-warn",
    "KI-Berichte oder Laufbericht-Finalisierung läuft",
)
_INCOMPLETE = ReportingStatusInfo(
    "incomplete",
    "Berichte unvollständig",
    "badge-incomplete",
    "Finalisierung abgebrochen — .pending_run.json liegt noch im Ordner",
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
    )


def _reports_dir(run_path: Path) -> Path:
    return run_path / "Reports"


def _ki_session_active(run_path: Path) -> bool:
    try:
        from tslab.services.report_runner import ai_report_in_progress

        if ai_report_in_progress(run_path):
            return True
    except ImportError:
        pass
    return (_reports_dir(run_path) / SESSION_BASENAME).is_file()


def inspect_reporting_status(output_dir: str | Path | None) -> ReportingStatusInfo:
    """Status aus Dateisystem + aktivem Hintergrund-Thread ableiten."""
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

    if _ki_session_active(run_path):
        return _IN_PROGRESS

    if pending_path.is_file():
        return _INCOMPLETE

    return _COMPLETE
