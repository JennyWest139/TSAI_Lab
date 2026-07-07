"""Tests fuer Reporting-Status-Erkennung."""

from __future__ import annotations

import json
from pathlib import Path

from tslab.services.reporting_status import (
    SESSION_BASENAME,
    inspect_reporting_status,
    is_run_output_dir,
)
from tslab.services.run_telemetry import PENDING_BASENAME


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
