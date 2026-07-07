"""Tests fuer Reporting-Status-Erkennung."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from tslab.services.report_runner import KI_FAILED_BASENAME, abort_ki_run_by_user
from tslab.services.reporting_status import (
    SESSION_BASENAME,
    inspect_reporting_status,
    is_run_output_dir,
    ki_abort_available,
)
from tslab.services.run_telemetry import PENDING_BASENAME, RunTelemetryCollector, save_pending_collector


def test_is_run_output_dir_recognizes_tsa_prefix(tmp_path: Path) -> None:
    run = tmp_path / "TSA_ex_foo_2020-01-01_to_2021-01-01"
    run.mkdir()
    assert is_run_output_dir(run)


def test_complete_when_no_pending_files(tmp_path: Path) -> None:
    run = tmp_path / "TSA_ex_test"
    run.mkdir()
    (run / "Reports").mkdir()
    (run / "Reports" / "laufbericht.pdf").write_bytes(b"%PDF")
    status = inspect_reporting_status(run)
    assert status.code == "complete"


def test_incomplete_when_only_prep_and_pending(tmp_path: Path) -> None:
    run = tmp_path / "TSA_ex_test"
    reports = run / "Reports"
    reports.mkdir(parents=True)
    (reports / "prep_laufbericht.pdf").write_bytes(b"%PDF")
    (reports / PENDING_BASENAME).write_text(
        json.dumps({"run_type": "TSA", "started_at": "2026-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    status = inspect_reporting_status(run)
    assert status.code == "incomplete"


def test_incomplete_when_pending_without_session(tmp_path: Path) -> None:
    run = tmp_path / "TSA_ex_test"
    reports = run / "Reports"
    reports.mkdir(parents=True)
    (reports / PENDING_BASENAME).write_text(
        json.dumps({"run_type": "TSA", "started_at": "2026-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    status = inspect_reporting_status(run)
    assert status.code == "incomplete"
    assert status.badge_class == "badge-incomplete"


def test_in_progress_when_report_session_exists(tmp_path: Path) -> None:
    run = tmp_path / "CORR_ex_test"
    reports = run / "Reports"
    reports.mkdir(parents=True)
    (reports / SESSION_BASENAME).write_text("{}", encoding="utf-8")
    status = inspect_reporting_status(run)
    assert status.code == "in_progress"
    assert not status.abort_available


def test_abort_available_when_stale_session(tmp_path: Path) -> None:
    run = tmp_path / "TSA_ex_stale"
    reports = run / "Reports"
    reports.mkdir(parents=True)
    collector = RunTelemetryCollector(run_type="TSA")
    collector.set_output(run)
    save_pending_collector(collector, run)
    session = reports / SESSION_BASENAME
    session.write_text(
        json.dumps(
            {
                "version": 1,
                "model_label": "GPT-4o mini",
                "targets": [{"rel_path": "arma11", "title": "ARMA", "done": False, "tasks": []}],
                "current_target": 0,
                "llm_calls_total": 3,
                "token_usage": {"total_tokens": 1200},
                "completed_reports": [],
            }
        ),
        encoding="utf-8",
    )
    old = time.time() - 7200
    os.utime(session, (old, old))

    status = inspect_reporting_status(run)
    assert status.code == "stalled"
    assert status.abort_available
    assert ki_abort_available(run)


def test_abort_ki_run_by_user_writes_report(tmp_path: Path) -> None:
    run = tmp_path / "TSA_ex_abort"
    reports = run / "Reports"
    reports.mkdir(parents=True)
    collector = RunTelemetryCollector(run_type="TSA")
    collector.set_output(run)
    save_pending_collector(collector, run)
    session = reports / SESSION_BASENAME
    session.write_text(
        json.dumps(
            {
                "version": 1,
                "model_label": "GPT-4o mini",
                "targets": [{"rel_path": "arma11", "title": "ARMA", "done": False, "tasks": []}],
                "current_target": 0,
                "llm_calls_total": 1,
                "token_usage": {"total_tokens": 50},
                "completed_reports": [],
            }
        ),
        encoding="utf-8",
    )
    old = time.time() - 7200
    os.utime(session, (old, old))

    result = abort_ki_run_by_user(run)
    assert result["ok"]
    assert "Nutzer manuell beendet" in result["message"]
    assert not session.is_file()
    assert not (reports / PENDING_BASENAME).is_file()
    assert (reports / "laufbericht.pdf").is_file()
    assert (reports / KI_FAILED_BASENAME).is_file()

    status = inspect_reporting_status(run)
    assert status.code == "failed"
    assert "Nutzer manuell beendet" in status.detail


def test_complete_when_final_report_and_orphan_session(tmp_path: Path) -> None:
    run = tmp_path / "TSA_ex_xrp"
    reports = run / "Reports"
    reports.mkdir(parents=True)
    (reports / "laufbericht.pdf").write_bytes(b"%PDF")
    (reports / SESSION_BASENAME).write_text("{}", encoding="utf-8")

    status = inspect_reporting_status(run)
    assert status.code == "complete"
    assert status.badge_class == "badge-ok"
    assert not (reports / SESSION_BASENAME).is_file()
