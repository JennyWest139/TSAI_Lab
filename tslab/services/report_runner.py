"""KI-Berichtssession serverseitig bis zum Ende ausfuehren (Hintergrund-Thread)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from tslab.services.output_paths import browse_url_for, resolve_output_dir_arg
from tslab.services.report_session import prepare_report_session, step_report_session
from tslab.services.run_telemetry import (
    clear_pending_collector,
    langfuse_status_from_config,
    load_pending_collector,
)
from tslab.services.report_service import load_report_config

_log = logging.getLogger(__name__)

_active_threads: dict[str, threading.Thread] = {}
_registry_lock = threading.Lock()

_MAX_STEP_ITERATIONS = 500


def run_report_session_to_completion(
    output_dir: str | Path,
    *,
    model_id: str | None,
    run_type: str,
    analysis_mode: str = "extended",
    auto_pause: bool = True,
) -> dict[str, Any]:
    """Prepare + step-Schleife bis fertig oder Fehler."""
    prep = prepare_report_session(
        output_dir,
        model_id=model_id,
        run_type=run_type,
        analysis_mode=analysis_mode,
    )
    if not prep.get("ok"):
        return prep

    for _ in range(_MAX_STEP_ITERATIONS):
        step = step_report_session(output_dir, auto_pause=auto_pause)
        status = step.get("status")
        if status == "done":
            return step
        if not step.get("ok"):
            return step
        if status == "awaiting_user":
            step = step_report_session(output_dir, action="pause", auto_pause=auto_pause)
            if step.get("status") == "done":
                return step
            if not step.get("ok"):
                return step
    return {
        "ok": False,
        "status": "error",
        "message": "KI-Bericht: maximale Schrittzahl erreicht.",
    }


def _finalize_pending_run(
    output_dir: str | Path,
    *,
    report_result: dict[str, Any] | None,
) -> None:
    from tslab.services.run_telemetry import RunTelemetryCollector

    run_path = str(resolve_output_dir_arg(output_dir))
    collector = load_pending_collector(run_path)
    if collector is None:
        _log.warning("KI-Hintergrund: kein Pending-Lauf fuer %s", run_path)
        return

    browse = browse_url_for(run_path)
    collector.set_output(run_path, browse_url=browse)
    collector.set_langfuse_status(langfuse_status_from_config(load_report_config()))

    if report_result and report_result.get("ok"):
        collector.merge_ai_session_result(report_result)
        msg = report_result.get("message") or "KI-Berichte erstellt."
        _log.info("KI-Hintergrund fertig: %s — %s", run_path, msg)
    elif report_result:
        collector.warning(str(report_result.get("message") or "KI-Bericht fehlgeschlagen."))
        _log.warning("KI-Hintergrund Fehler: %s — %s", run_path, report_result.get("message"))

    collector.write_pdf()
    clear_pending_collector(run_path)


def _background_worker(
    output_dir: str,
    *,
    model_id: str | None,
    run_type: str,
    analysis_mode: str,
) -> None:
    key = output_dir
    try:
        report_result = run_report_session_to_completion(
            output_dir,
            model_id=model_id,
            run_type=run_type,
            analysis_mode=analysis_mode,
            auto_pause=True,
        )
        _finalize_pending_run(output_dir, report_result=report_result)
    except Exception:
        _log.exception("KI-Hintergrund-Lauf fehlgeschlagen: %s", output_dir)
        try:
            collector = load_pending_collector(output_dir)
            if collector:
                collector.error("KI-Bericht: unerwarteter Hintergrund-Fehler.")
                collector.set_output(output_dir, browse_url=browse_url_for(output_dir))
                collector.write_pdf()
        except Exception:
            _log.exception("KI-Hintergrund: Laufbericht nach Fehler nicht schreibbar.")
        finally:
            clear_pending_collector(output_dir)
    finally:
        with _registry_lock:
            _active_threads.pop(key, None)


def start_background_ai_reports(
    output_dir: str | Path,
    *,
    model_id: str | None,
    run_type: str,
    analysis_mode: str = "extended",
) -> bool:
    """Startet KI-Berichte in einem Daemon-Thread; gibt False zurueck wenn bereits aktiv."""
    run_path = str(resolve_output_dir_arg(output_dir))
    if not model_id:
        return False

    with _registry_lock:
        existing = _active_threads.get(run_path)
        if existing is not None and existing.is_alive():
            return False
        thread = threading.Thread(
            target=_background_worker,
            kwargs={
                "output_dir": run_path,
                "model_id": model_id,
                "run_type": run_type,
                "analysis_mode": analysis_mode,
            },
            daemon=True,
            name=f"tslab-ai-report-{Path(run_path).name[:40]}",
        )
        _active_threads[run_path] = thread
        thread.start()
    return True


def ai_report_in_progress(output_dir: str | Path) -> bool:
    run_path = str(resolve_output_dir_arg(output_dir))
    with _registry_lock:
        thread = _active_threads.get(run_path)
        return thread is not None and thread.is_alive()
