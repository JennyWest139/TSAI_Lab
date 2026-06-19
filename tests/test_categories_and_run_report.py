"""Tests fuer Kategorien und Laufberichte."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tslab.services.run_report_pdf import write_run_report_pdf
from tslab.services.run_telemetry import RunTelemetry, RunTelemetryCollector, ComponentTiming
from tslab.web import mock_data as mock


class MockCategoryTests(unittest.TestCase):
    def setUp(self) -> None:
        mock._mock_categories[:] = [{"id": 1, "name": mock.PROTECTED_CATEGORY}]
        mock._mock_series_category.clear()
        mock._mock_next_category_id = 2

    def test_create_and_assign(self) -> None:
        created = mock.mock_create_category("Makro")
        self.assertEqual(created["name"], "Makro")
        cats = mock.mock_list_categories()
        self.assertTrue(any(c["name"] == "Makro" for c in cats))
        result = mock.mock_update_series_meta("pdax", name="PDAX", category_id=created["id"])
        self.assertEqual(result["series"]["category_name"], "Makro")
        filtered = mock.mock_list_series(category_id=created["id"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].slug, "pdax")

    def test_reporting_protected(self) -> None:
        with self.assertRaises(ValueError):
            mock.mock_update_category(1, "Other")


class RunReportPdfTests(unittest.TestCase):
    def test_write_pdf(self) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        telemetry = RunTelemetry(
            run_type="Korrelation",
            started_at=now,
            output_dir="/tmp/test_run",
            components=[
                ComponentTiming("job", 123.4, started_at=now, ended_at=now),
            ],
            warnings=["Test-Warnung"],
            errors=[],
            langfuse={"configured": False, "note": "inaktiv"},
            links={"Output": "/output/browse/test"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "laufbericht.pdf"
            write_run_report_pdf(path, telemetry)
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 500)


class RunTelemetryCollectorTests(unittest.TestCase):
    def test_track_and_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run_out"
            out.mkdir()
            (out / "summary.txt").write_text("test", encoding="utf-8")
            collector = RunTelemetryCollector(run_type="Test")
            with collector.track("step_a"):
                pass
            collector.set_output(out)
            result = collector.write_pdf()
            self.assertTrue(result["ok"])
            self.assertTrue((out / "Reports" / "laufbericht.pdf").is_file())


if __name__ == "__main__":
    unittest.main()
