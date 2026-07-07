"""Hintergrund-KI darf sich bei prepare nicht selbst blockieren."""

from __future__ import annotations

import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tslab.services import report_runner
from tslab.services.report_runner import background_model_matches
from tslab.services.report_session import prepare_report_session


class BackgroundPrepareTests(unittest.TestCase):
    def test_background_model_tracking(self) -> None:
        self.assertFalse(
            background_model_matches("/nonexistent", "openai:gpt-4o-mini")
        )

    def test_prepare_not_blocked_for_current_worker_thread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "summary.txt").write_text("corr", encoding="utf-8")
            (root / "plot.png").write_bytes(b"png")

            barrier = threading.Barrier(2, timeout=5)
            result: dict = {}

            def worker() -> None:
                report_runner._active_threads[str(root.resolve())] = threading.current_thread()
                try:
                    barrier.wait()
                    result["prep"] = prepare_report_session(
                        root,
                        model_id="openai:gpt-4o-mini",
                        run_type="Korrelation",
                        analysis_mode="extended",
                    )
                finally:
                    report_runner._active_threads.pop(str(root.resolve()), None)

            thread = threading.Thread(target=worker)
            with patch.object(report_runner, "ai_report_in_progress", return_value=True):
                thread.start()
                barrier.wait()
                thread.join(timeout=10)

            self.assertIn("prep", result)
            self.assertNotEqual(result["prep"].get("status"), "in_progress")
            self.assertIn(result["prep"].get("status"), ("ready", "disabled", "error"))


if __name__ == "__main__":
    unittest.main()
