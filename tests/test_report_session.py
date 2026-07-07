"""Tests fuer schrittweise KI-Berichtssessions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tslab.services.report_session import (
    CHECKPOINT_CALLS,
    _build_tsa_comparison_target,
    discover_report_targets,
    filter_model_dirs_for_comparison,
    list_tsa_model_dirs,
    prepare_report_session,
    summary_text_for_model_comparison,
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

    def test_tsa_comparison_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("arma11", "garch11"):
                d = root / name
                d.mkdir()
                (d / "summary.txt").write_text(f"summary {name}", encoding="utf-8")
            model_dirs = list_tsa_model_dirs(root)
            cmp_target = _build_tsa_comparison_target(
                root, model_dirs, ai_suffix="GPT-4o-mini"
            )
            self.assertIsNotNone(cmp_target)
            assert cmp_target is not None
            self.assertEqual(cmp_target.rel_path, "Reports")
            self.assertEqual(
                cmp_target.output_basename, "Modellvergleich_GPT-4o-mini.docx"
            )
            self.assertEqual(len(cmp_target.tasks), 2)
            self.assertEqual(cmp_target.report_layout, "tsa_comparison")
            self.assertEqual(cmp_target.text_sections, [])
            bundle = cmp_target.tasks[0].payload.get("parts") or []
            self.assertTrue(all("Prognose PDAX-Niveau" not in p for p in bundle))

    def test_summary_strips_forecast_level_table(self) -> None:
        raw = (
            "Modell: ARMA(1,1)\nAIC: -100\n\n"
            "Prognose PDAX-Niveau (Ruecktransformation aus log-Renditen)\n"
            "Datum          Mittelwert    q0.5%\n"
            "2026-01-01        9.70      8.31\n"
        )
        trimmed = summary_text_for_model_comparison(raw)
        self.assertIn("AIC", trimmed)
        self.assertNotIn("Prognose PDAX", trimmed)
        self.assertNotIn("9.70", trimmed)

    def test_filter_model_dirs_by_ui_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("arma11", "garch11", "decomp_additive"):
                d = root / name
                d.mkdir()
                (d / "summary.txt").write_text("s", encoding="utf-8")
            reports = root / "Reports"
            reports.mkdir()
            pending = {
                "run_type": "TSA",
                "started_at": "2026-01-01T00:00:00+00:00",
                "components": [],
                "warnings": [],
                "errors": [],
                "tokens": {},
                "extra": {
                    "ui_settings": [
                        {"label": "Modelle", "value": "arma, garch"},
                    ]
                },
            }
            import json

            (reports / ".pending_run.json").write_text(
                json.dumps(pending), encoding="utf-8"
            )
            all_dirs = list_tsa_model_dirs(root)
            filtered = filter_model_dirs_for_comparison(root, all_dirs)
            self.assertEqual([d.name for d in filtered], ["arma11", "garch11"])

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
