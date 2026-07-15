"""Tests fuer UI-Einstellungen im Laufbericht."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tslab.services.run_report_pdf import write_run_report_pdf
from tslab.services.run_settings import build_correlation_run_settings, build_tsa_run_settings
from tslab.services.run_telemetry import RunTelemetry, RunTelemetryCollector


class RunSettingsTests(unittest.TestCase):
    def test_build_correlation_settings(self) -> None:
        rows = build_correlation_run_settings(
            {"report_model": ""},
            series_a="pdax",
            series_b="dax",
            analysis_mode="extended",
            start_date="2020-01-01",
            end_date="2024-12-31",
            max_lag=24,
            frequency="MS",
            run_name="PDAX_vs_DAX",
        )
        labels = [r[0] for r in rows]
        self.assertIn("Serie A", labels)
        self.assertIn("KI-Bericht", labels)
        self.assertEqual(dict(rows)["KI-Bericht"], "Ohne KI")

    def test_build_tsa_settings_includes_quantiles(self) -> None:
        rows = build_tsa_run_settings(
            {
                "report_model": "openai:gpt-4o-mini",
                "plot_pre_years": "3",
                "plot_forecast_years": "1",
                "plot_post_years": "1",
            },
            series_slug="avax",
            analysis_mode="thesis",
            models=["arma", "garch"],
            train_start="2020-01-01",
            train_end="2024-12-31",
            forecast_end="2025-12-31",
            order_mode="auto",
            quantiles=(0.05, 0.5, 0.95),
        )
        data = dict(rows)
        self.assertEqual(data["Zeitreihe"], "avax")
        self.assertIn("0.05", data["Quantile"])


class RunReportUiSettingsPdfTests(unittest.TestCase):
    def test_pdf_includes_ui_settings_chapter(self) -> None:
        now = datetime.now(timezone.utc)
        telemetry = RunTelemetry(
            run_type="TSA",
            started_at=now,
            extra={
                "ui_settings": [
                    {"label": "Zeitreihe", "value": "pdax"},
                    {"label": "KI-Bericht", "value": "Ohne KI"},
                ]
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "laufbericht.pdf"
            write_run_report_pdf(path, telemetry)
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 400)

    def test_pdf_includes_corr_ui_settings_chapter(self) -> None:
        now = datetime.now(timezone.utc)
        rows = build_correlation_run_settings(
            {"report_model": "gemini:gemini-2.5-flash"},
            series_a="avax_close",
            series_b="ada_close",
            analysis_mode="extended",
            start_date="2020-01-01",
            end_date="2026-06-30",
            max_lag=12,
            frequency="MS",
            run_name="AVAX_vs_ADA",
        )
        telemetry = RunTelemetry(
            run_type="Korrelation",
            started_at=now,
            extra={"ui_settings": [{"label": k, "value": v} for k, v in rows]},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "laufbericht.pdf"
            write_run_report_pdf(path, telemetry)
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 400)

    def test_collector_persists_ui_settings_in_pending(self) -> None:
        from tests.helpers_output import temp_output_run
        from tslab.services.run_telemetry import load_pending_collector, save_pending_collector

        with temp_output_run("pending_ui_run") as out:
            collector = RunTelemetryCollector(run_type="Korrelation")
            collector.set_run_settings([("Serie A", "pdax"), ("Serie B", "dax")])
            save_pending_collector(collector, out)
            loaded = load_pending_collector(out)
            assert loaded is not None
            settings = loaded.data.extra.get("ui_settings") or []
            self.assertEqual(len(settings), 2)
            self.assertEqual(settings[0]["label"], "Serie A")


if __name__ == "__main__":
    unittest.main()
