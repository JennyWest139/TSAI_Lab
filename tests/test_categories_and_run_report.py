"""Tests fuer Tags (Kategorien) und Laufberichte."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tslab.services.run_report_pdf import write_run_report_pdf
from tslab.services.run_telemetry import RunTelemetry, RunTelemetryCollector, ComponentTiming
from tslab.web import mock_data as mock


class MockTagTests(unittest.TestCase):
    def setUp(self) -> None:
        mock._mock_categories[:] = [{"id": 1, "name": mock.PROTECTED_CATEGORY}]
        mock._mock_series_categories.clear()
        mock._mock_run_categories.clear()
        mock._mock_next_category_id = 2

    def test_create_and_assign(self) -> None:
        created = mock.mock_create_category("Makro")
        self.assertEqual(created["name"], "Makro")
        tags = mock.mock_all_tags()
        self.assertIn("Makro", tags)
        mock.mock_set_entity_categories("series", "pdax", [created["id"]])
        mock.mock_update_series_meta("pdax", name="PDAX")
        s = mock.series_by_slug("pdax")
        assert s is not None
        self.assertIn("Makro", s.tags)
        filtered = mock.mock_list_series(tag="Makro")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].slug, "pdax")

    def test_reporting_protected(self) -> None:
        with self.assertRaises(ValueError):
            mock.mock_update_category(1, "Other")

    def test_run_tags_inherit(self) -> None:
        makro = mock.mock_create_category("Makro")
        mock.mock_set_entity_categories("series", "pdax", [1, makro["id"]])
        ids = mock.mock_inherit_run_categories("correlation", 99, ["pdax"])
        self.assertIn(1, ids)
        self.assertIn(makro["id"], ids)


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
