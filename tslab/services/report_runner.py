"""KI-Berichtssession serverseitig bis zum Ende ausfuehren (Hintergrund-Thread)."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tslab.services.output_paths import browse_url_for, output_ref, relative_output_path, resolve_output_dir_arg
from tslab.services.report_session import (
    load_session,
    prepare_report_session,
    step_report_session,
)
from tslab.services.run_telemetry import (
    clear_pending_collector,
    langfuse_status_from_config,
    load_pending_collector,
)
from tslab.services.report_service import load_report_config

_log = logging.getLogger(__name__)

_active_threads: dict[str, threading.Thread] = {}
_active_thread_models: dict[str, str] = {}
_abort_events: dict[str, threading.Event] = {}
_user_abort_messages: dict[str, str] = {}
_finalize_locks: dict[str, threading.RLock] = {}
_registry_lock = threading.Lock()
_finalize_locks_guard = threading.Lock()

_MAX_STEP_ITERATIONS = 500
_BACKGROUND_JOIN_TIMEOUT_S = 600.0
_USER_ABORT_JOIN_TIMEOUT_S = 45.0
STALE_KI_SESSION_MINUTES = 30
KI_FAILED_BASENAME = ".ki_run_failed.json"


def _registry_key(output_dir: str | Path) -> str:
    return output_ref(output_dir)


def _reports_dir(run_path: Path) -> Path:
    return run_path / "Reports"


def ki_failed_marker_path(run_path: str | Path) -> Path:
    return _reports_dir(resolve_output_dir_arg(run_path)) / KI_FAILED_BASENAME


def write_ki_failed_marker(
    run_path: str | Path,
    message: str,
    *,
    reason: str = "",
) -> None:
    path = ki_failed_marker_path(run_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "message": message.strip(),
        "reason": reason.strip(),
        "finalized_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_ki_failed_marker(run_path: str | Path) -> None:
    path = ki_failed_marker_path(run_path)
    if path.is_file():
        path.unlink()


def _finalize_lock_for(run_path_str: str) -> threading.RLock:
    with _finalize_locks_guard:
        lock = _finalize_locks.get(run_path_str)
        if lock is None:
            lock = threading.RLock()
            _finalize_locks[run_path_str] = lock
        return lock


def _abort_event_for(run_path_str: str) -> threading.Event:
    with _registry_lock:
        event = _abort_events.get(run_path_str)
        if event is None:
            event = threading.Event()
            _abort_events[run_path_str] = event
        return event


def is_ki_abort_requested(output_dir: str | Path) -> bool:
    run_path_str = output_ref(output_dir)
    with _registry_lock:
        event = _abort_events.get(run_path_str)
        return event is not None and event.is_set()


def _peek_user_abort_message(run_path_str: str) -> str | None:
    with _registry_lock:
        msg = _user_abort_messages.get(run_path_str)
        return msg.strip() if msg else None


def _pop_user_abort_message(run_path_str: str) -> str | None:
    with _registry_lock:
        return _user_abort_messages.pop(run_path_str, None)


def _clear_abort_state(run_path_str: str) -> None:
    with _registry_lock:
        _abort_events.pop(run_path_str, None)
        _user_abort_messages.pop(run_path_str, None)


def _user_abort_message() -> str:
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    return f"KI-Berichte vom Nutzer manuell beendet am {now}."


def _message_from_session_state(state: Any | None) -> str:
    if state is None:
        return "KI-Bericht abgebrochen (keine Session-Details)."
    done = sum(1 for t in state.targets if t.done)
    total = len(state.targets)
    model = state.model_label or state.model_id or "unbekanntes Modell"
    parts = [
        f"KI-Bericht abgebrochen ({model})",
        f"Fortschritt: {done}/{total} Ziele",
    ]
    if total and 0 <= state.current_target < total and not state.targets[state.current_target].done:
        title = str(state.targets[state.current_target].title or "").strip()
        if title:
            parts.append(f"unterbrochen bei „{title}“")
    if state.llm_calls_total:
        parts.append(f"{state.llm_calls_total} LLM-Aufrufe")
    total_tokens = int((state.token_usage or {}).get("total_tokens") or 0)
    if total_tokens:
        parts.append(f"{total_tokens:,} Token".replace(",", "."))
    return ". ".join(parts) + "."


def finalize_aborted_ki_run(
    output_dir: str | Path,
    *,
    reason: str | None = None,
    reconcile_reason: str = "stale_session",
) -> str:
    """Schreibt finalen Laufbericht mit Fehler, raeumt Session/Pending auf."""
    from tslab.services.report_session import delete_session, load_session

    run_path = resolve_output_dir_arg(output_dir)
    run_path_str = output_ref(run_path)
    session_path = _reports_dir(run_path) / ".report_session.json"
    with _finalize_lock_for(run_path_str):
        if not load_pending_collector(run_path) and not session_path.is_file():
            existing = _peek_user_abort_message(run_path_str)
            if existing:
                write_ki_failed_marker(run_path_str, existing, reason=reconcile_reason)
                return existing
        state = load_session(run_path)
        message = (reason or _message_from_session_state(state)).strip()

        collector = load_pending_collector(run_path)
        if collector is None:
            delete_session(run_path)
            write_ki_failed_marker(run_path_str, message, reason=reconcile_reason)
            return message

        collector.set_output(run_path, browse_url=browse_url_for(run_path_str))
        collector.set_langfuse_status(langfuse_status_from_config(load_report_config()))
        collector.error(message)
        collector.data.extra["ki_report_status"] = "failed"
        if reconcile_reason == "user_abort":
            collector.data.extra["ki_user_aborted"] = True
            collector.data.extra["ki_user_abort_at"] = datetime.now(timezone.utc).isoformat()

        partial = _partial_session_result(run_path)
        if partial and partial.get("ok"):
            collector.warning(str(partial.get("message") or "Teilweise KI-Berichte erzeugt."))
            collector.merge_ai_session_result(partial)
            collector.data.extra["ki_report_status"] = "partial"
        elif partial:
            collector.merge_ai_session_result(partial)

        if state is not None:
            for target in state.targets:
                for err in target.ai_errors:
                    collector.error(str(err))
                for warn in target.ai_warnings:
                    collector.warning(str(warn))

        collector.write_pdf(variant="final")
        clear_pending_collector(run_path)
        delete_session(run_path)
        write_ki_failed_marker(run_path_str, message, reason=reconcile_reason)
        _log.warning("KI-Lauf abgebrochen finalisiert: %s — %s", run_path_str, message)
        return message


def abort_ki_run_by_user(output_dir: str | Path) -> dict[str, Any]:
    """Beendet einen haengenden KI-Lauf manuell und schreibt den finalen Laufbericht."""
    from tslab.services.report_session import RateLimitEvent, delete_session, load_session, save_session
    from tslab.services.reporting_status import inspect_reporting_status, ki_abort_available

    run_path = resolve_output_dir_arg(output_dir)
    run_path_str = output_ref(run_path)

    if not ki_abort_available(run_path):
        return {
            "ok": False,
            "message": (
                f"„Jetzt beenden“ ist erst nach {STALE_KI_SESSION_MINUTES} Minuten "
                "ohne Fortschritt verfügbar."
            ),
        }

    user_msg = _user_abort_message()
    with _registry_lock:
        _user_abort_messages[run_path_str] = user_msg
    _abort_event_for(run_path_str).set()

    state = load_session(run_path)
    if state is not None:
        state.finish_early = True
        state.rate_limit_events.append(
            RateLimitEvent(
                at_call=state.llm_calls_total,
                user_choice="finish",
                paused_seconds=0,
                reason="user_abort",
            )
        )
        save_session(state, run_path)

    join_background_ai_reports(run_path, timeout=_USER_ABORT_JOIN_TIMEOUT_S)

    reports = _reports_dir(run_path)
    pending_exists = load_pending_collector(run_path) is not None
    session_exists = (reports / ".report_session.json").is_file()
    if pending_exists or session_exists:
        state = load_session(run_path)
        detail = _message_from_session_state(state)
        full_msg = f"{user_msg} {detail}".strip()
        with _finalize_lock_for(run_path_str):
            if load_pending_collector(run_path) is not None or (reports / ".report_session.json").is_file():
                finalize_aborted_ki_run(
                    run_path,
                    reason=full_msg,
                    reconcile_reason="user_abort",
                )
            else:
                write_ki_failed_marker(run_path_str, full_msg, reason="user_abort")
    else:
        write_ki_failed_marker(run_path_str, user_msg, reason="user_abort")

    _clear_abort_state(run_path_str)
    delete_session(run_path)

    status = inspect_reporting_status(run_path)
    rel = relative_output_path(run_path)
    run_report_url = f"/output/file/{rel}/Reports/laufbericht.pdf" if rel else None
    return {
        "ok": True,
        "message": user_msg,
        "reporting_status": status.to_dict(),
        "run_report_url": run_report_url,
        "browse_url": browse_url_for(run_path_str),
    }


def _session_result_from_state(state: Any) -> dict[str, Any]:
    reports = list(state.completed_reports)
    combined_errors: list[str] = []
    for report in reports:
        combined_errors.extend(report.get("ai_errors") or [])
    return {
        "ok": bool(reports),
        "status": "done" if reports else "error",
        "message": (
            f"{len(reports)} KI-Bericht(e) erstellt."
            if reports
            else "KI-Bericht: keine fertigen Zielberichte."
        ),
        "reports": reports,
        "report": reports[0] if len(reports) == 1 else None,
        "llm_calls": state.llm_calls_total,
        "rate_limit_events": [e.to_dict() for e in state.rate_limit_events],
        "rate_limit_pause_count": sum(
            1 for e in state.rate_limit_events if e.user_choice == "pause"
        ),
        "ai_errors": combined_errors,
        "token_usage": {
            **state.token_usage,
            "model": state.model_label,
            "calls": state.llm_calls_total,
        },
        "langfuse_active": state.langfuse_active,
    }


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
    if prep.get("status") == "in_progress":
        return {
            "ok": False,
            "status": "in_progress",
            "message": str(prep.get("message") or "KI-Berichte laufen bereits."),
        }

    for _ in range(_MAX_STEP_ITERATIONS):
        if is_ki_abort_requested(output_dir):
            step = step_report_session(output_dir, action="finish", auto_pause=auto_pause)
            user_msg = _peek_user_abort_message(output_ref(output_dir)) or _user_abort_message()
            if step.get("status") == "done":
                step["ok"] = False
                step["message"] = user_msg
                return step
            partial = _partial_session_result(output_dir)
            result: dict[str, Any] = {
                "ok": False,
                "status": "aborted",
                "message": user_msg,
            }
            if partial:
                result.update(partial)
                result["ok"] = False
                result["message"] = user_msg
            return result
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
    partial = _partial_session_result(output_dir)
    if partial:
        return partial
    return {
        "ok": False,
        "status": "error",
        "message": "KI-Bericht: maximale Schrittzahl erreicht.",
    }


def _partial_session_result(output_dir: str | Path) -> dict[str, Any] | None:
    run_path = resolve_output_dir_arg(output_dir)
    state = load_session(run_path)
    if state is None or not state.completed_reports:
        return None
    result = _session_result_from_state(state)
    result["message"] = str(result.get("message") or "") + " (teilweise)"
    return result


def _finalize_pending_run(
    output_dir: str | Path,
    *,
    report_result: dict[str, Any] | None,
) -> None:
    from tslab.services.report_session import delete_session

    run_path = str(resolve_output_dir_arg(output_dir))
    with _finalize_lock_for(run_path):
        collector = load_pending_collector(run_path)
        if collector is None:
            _log.warning("KI-Hintergrund: kein Pending-Lauf fuer %s", run_path)
            delete_session(run_path)
            return

        browse = browse_url_for(run_path)
        collector.set_output(run_path, browse_url=browse)
        collector.set_langfuse_status(langfuse_status_from_config(load_report_config()))
        ki_status = "ok"
        user_abort = _pop_user_abort_message(run_path)

        if user_abort:
            collector.error(user_abort)
            collector.data.extra["ki_user_aborted"] = True
            collector.data.extra["ki_user_abort_at"] = datetime.now(timezone.utc).isoformat()
            ki_status = "failed"
            write_ki_failed_marker(run_path, user_abort, reason="user_abort")
            partial = _partial_session_result(run_path)
            if partial and partial.get("ok"):
                collector.warning(str(partial.get("message") or "Teilweise KI-Berichte erzeugt."))
                collector.merge_ai_session_result(partial)
                if partial.get("reports"):
                    ki_status = "partial"
            elif partial:
                collector.merge_ai_session_result(partial)
        elif report_result and report_result.get("ok"):
            clear_ki_failed_marker(run_path)
            expected = str(collector.data.extra.get("report_model_id") or "").strip()
            reports = list(report_result.get("reports") or [])
            if not reports and report_result.get("report"):
                reports = [report_result["report"]]
            used_id = str(reports[0].get("model") or "").strip() if reports else ""
            if expected and used_id and expected != used_id:
                collector.warning(
                    f"KI-Modell-Abweichung: gewaehlt {expected}, erzeugt mit {used_id}."
                )
            collector.merge_ai_session_result(report_result)
            msg = str(report_result.get("message") or "KI-Berichte erstellt.")
            if "teilweise" in msg.lower():
                ki_status = "partial"
                collector.warning(msg)
            _log.info("KI-Hintergrund fertig: %s — %s", run_path, msg)
        elif report_result:
            partial = _partial_session_result(run_path)
            if partial and partial.get("ok"):
                ki_status = "partial"
                collector.merge_ai_session_result(partial)
                collector.warning(str(partial.get("message") or "KI-Berichte nur teilweise erstellt."))
                _log.warning(
                    "KI-Hintergrund teilweise: %s — %s",
                    run_path,
                    partial.get("message"),
                )
            else:
                ki_status = "failed"
                failure_message = str(report_result.get("message") or "KI-Bericht fehlgeschlagen.")
                collector.error(failure_message)
                if partial:
                    collector.merge_ai_session_result(partial)
                write_ki_failed_marker(run_path, failure_message, reason="background_error")
                _log.warning("KI-Hintergrund Fehler: %s — %s", run_path, failure_message)
        else:
            ki_status = "failed"
            failure_message = "KI-Bericht: Finalisierung ohne Ergebnis."
            collector.error(failure_message)
            write_ki_failed_marker(run_path, failure_message, reason="missing_result")

        collector.data.extra["ki_report_status"] = ki_status
        collector.write_pdf(variant="final")
        clear_pending_collector(run_path)
        delete_session(run_path)


def _background_worker(
    output_dir: str,
    *,
    model_id: str | None,
    run_type: str,
    analysis_mode: str,
) -> None:
    key = output_dir
    report_result: dict[str, Any] | None = None
    try:
        report_result = run_report_session_to_completion(
            output_dir,
            model_id=model_id,
            run_type=run_type,
            analysis_mode=analysis_mode,
            auto_pause=True,
        )
    except Exception:
        _log.exception("KI-Hintergrund-Lauf fehlgeschlagen: %s", output_dir)
        report_result = {
            "ok": False,
            "status": "error",
            "message": "KI-Bericht: unerwarteter Hintergrund-Fehler.",
        }
    finally:
        try:
            if report_result and not report_result.get("ok"):
                partial = _partial_session_result(output_dir)
                if partial and partial.get("ok"):
                    report_result = partial
            _finalize_pending_run(output_dir, report_result=report_result)
        except Exception:
            _log.exception("KI-Hintergrund: Finalisierung fehlgeschlagen: %s", output_dir)
            try:
                collector = load_pending_collector(output_dir)
                if collector:
                    msg = "KI-Bericht: Finalisierung fehlgeschlagen."
                    collector.error(msg)
                    collector.data.extra["ki_report_status"] = "failed"
                    collector.set_output(output_dir, browse_url=browse_url_for(output_dir))
                    collector.write_pdf(variant="final")
                    clear_pending_collector(output_dir)
                    write_ki_failed_marker(output_dir, msg, reason="finalize_exception")
                    from tslab.services.report_session import delete_session

                    delete_session(output_dir)
            except Exception:
                _log.exception("KI-Hintergrund: Laufbericht nach Fehler nicht schreibbar.")
        with _registry_lock:
            _active_threads.pop(key, None)
            _active_thread_models.pop(key, None)


def join_background_ai_reports(
    output_dir: str | Path, *, timeout: float | None = _BACKGROUND_JOIN_TIMEOUT_S
) -> bool:
    """Wartet auf den KI-Hintergrund-Thread fuer diesen Ordner (falls aktiv)."""
    run_path = str(resolve_output_dir_arg(output_dir))
    with _registry_lock:
        thread = _active_threads.get(run_path)
    if thread is None or not thread.is_alive():
        return True
    thread.join(timeout=timeout)
    return not thread.is_alive()


def active_background_model_id(output_dir: str | Path) -> str | None:
    run_path = str(resolve_output_dir_arg(output_dir))
    with _registry_lock:
        thread = _active_threads.get(run_path)
        if thread is None or not thread.is_alive():
            return None
        return _active_thread_models.get(run_path)


def background_model_matches(output_dir: str | Path, model_id: str | None) -> bool:
    active = active_background_model_id(output_dir)
    if not active:
        return False
    return active == str(model_id or "").strip()


def start_background_ai_reports(
    output_dir: str | Path,
    *,
    model_id: str | None,
    run_type: str,
    analysis_mode: str = "extended",
) -> bool:
    """Startet KI-Berichte in einem Daemon-Thread; gibt False zurueck wenn bereits aktiv."""
    from tslab.services.report_naming import ai_model_filename_suffix, purge_ai_reports_for_other_models
    from tslab.services.report_service import _model_spec_for_id, load_report_config
    from tslab.services.report_session import delete_session

    run_path = resolve_output_dir_arg(output_dir)
    run_path_str = output_ref(run_path)
    if not model_id:
        return False

    config = load_report_config()
    spec = _model_spec_for_id(config, model_id, output_dir=run_path)
    ai_suffix = ai_model_filename_suffix(model_label=spec.label, model_id=spec.id)

    with _registry_lock:
        existing = _active_threads.get(run_path_str)
        active_mid = _active_thread_models.get(run_path_str)
    if existing is not None and existing.is_alive():
        if active_mid == spec.id:
            return False
        _log.warning(
            "KI-Hintergrund: anderer Modell-Lauf aktiv (%s), warte auf Abschluss vor %s",
            active_mid,
            spec.id,
        )
        if not join_background_ai_reports(run_path_str):
            return False

    delete_session(run_path)
    purge_ai_reports_for_other_models(run_path, keep_suffix=ai_suffix)
    _clear_abort_state(run_path_str)

    with _registry_lock:
        existing = _active_threads.get(run_path_str)
        if existing is not None and existing.is_alive():
            return False
        thread = threading.Thread(
            target=_background_worker,
            kwargs={
                "output_dir": run_path_str,
                "model_id": spec.id,
                "run_type": run_type,
                "analysis_mode": analysis_mode,
            },
            daemon=True,
            name=f"tslab-ai-report-{Path(run_path_str).name[:40]}",
        )
        _active_threads[run_path_str] = thread
        _active_thread_models[run_path_str] = spec.id
        thread.start()
    return True


def ai_report_in_progress(output_dir: str | Path) -> bool:
    run_path = str(resolve_output_dir_arg(output_dir))
    with _registry_lock:
        thread = _active_threads.get(run_path)
        return thread is not None and thread.is_alive()


def is_current_background_worker(output_dir: str | Path) -> bool:
    """True wenn der aktuelle Thread der registrierte KI-Hintergrund-Lauf ist."""
    run_path = str(resolve_output_dir_arg(output_dir))
    with _registry_lock:
        thread = _active_threads.get(run_path)
        return thread is not None and thread is threading.current_thread()
