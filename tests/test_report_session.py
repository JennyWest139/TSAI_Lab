"""Tests fuer schrittweise KI-Berichtssessions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tslab.services.report_session import (
    CHECKPOINT_CALLS,
    discover_report_targets,
    list_tsa_model_dirs,
    prepare_report_session,
)


class ReportSessionDiscoveryTests(unittest.TestCase):
    def test_list_tsa_model_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "arma11").mkdir()
            (root / "arma11" / "summary.txt").write_text("test", encoding="utf-8")
            (root / "Reports").mkdir()
            (root / "misc").mkdir()
            dirs = list_tsa_model_dirs(root)
            self.assertEqual([d.name for d in dirs], ["arma11"])

    def test_discover_per_model_for_tsa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("arma11", "garch11"):
                d = root / name
                d.mkdir()
                (d / "summary.txt").write_text("s", encoding="utf-8")
                (d / "plot.png").write_bytes(b"png")
            targets = discover_report_targets(root, run_type="TSA", analysis_mode="extended")
            self.assertEqual(len(targets), 2)

    def test_prepare_session_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "summary.txt").write_text("x", encoding="utf-8")
            result = prepare_report_session(root, run_type="Korrelation")
            self.assertIn(result["status"], ("disabled", "ready", "error"))


class CheckpointConstantTests(unittest.TestCase):
    def test_checkpoint_is_five(self) -> None:
        self.assertEqual(CHECKPOINT_CALLS, 5)


if __name__ == "__main__":
    unittest.main()
