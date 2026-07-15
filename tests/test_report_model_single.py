"""Nur ein KI-Modell pro Lauf — Bereinigung und Modell-Aufloesung."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tslab.services.report_naming import purge_ai_reports_for_other_models
from tslab.services.report_service import resolve_run_report_model_id
from tslab.services.run_telemetry import RunTelemetryCollector, save_pending_collector


class ReportModelSingleTests(unittest.TestCase):
    def test_purge_removes_other_model_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CORR_AI_Bericht_GPT-4o-mini.docx").write_text("a", encoding="utf-8")
            (root / "CORR_AI_Bericht_GPT-4o-mini.pdf").write_text("a", encoding="utf-8")
            (root / "CORR_AI_Bericht_Gemini-3.1-Flash-Lite.docx").write_text("b", encoding="utf-8")
            reports = root / "Reports"
            reports.mkdir()
            (reports / "Modellvergleich_GPT-4o-mini.pdf").write_text("c", encoding="utf-8")
            (reports / "Modellvergleich_Gemini-3.1-Flash-Lite.pdf").write_text("d", encoding="utf-8")

            removed = purge_ai_reports_for_other_models(
                root, keep_suffix="Gemini-3.1-Flash-Lite"
            )

            self.assertIn("CORR_AI_Bericht_GPT-4o-mini.docx", removed)
            self.assertTrue(
                any("Modellvergleich_GPT-4o-mini.pdf" in item for item in removed)
            )
            self.assertTrue((root / "CORR_AI_Bericht_Gemini-3.1-Flash-Lite.docx").is_file())
            self.assertFalse((root / "CORR_AI_Bericht_GPT-4o-mini.docx").exists())

    def test_resolve_model_from_pending_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            collector = RunTelemetryCollector(run_type="Korrelation")
            collector.data.extra["report_model_id"] = "gemini:gemini-3.1-flash-lite"
            save_pending_collector(collector, root)

            resolved = resolve_run_report_model_id(root, None)
            self.assertEqual(resolved, "gemini:gemini-3.1-flash-lite")

            explicit = resolve_run_report_model_id(
                root, "openai:gpt-4o-mini"
            )
            self.assertEqual(explicit, "openai:gpt-4o-mini")

    def test_resolve_without_pending_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(resolve_run_report_model_id(root, None))


if __name__ == "__main__":
    unittest.main()
