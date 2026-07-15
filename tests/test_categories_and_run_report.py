"""Tests fuer Laufberichte (Tags-CRUD laeuft ab P3 gegen PostgreSQL)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tslab.services.run_report_pdf import write_run_report_pdf
from tslab.services.run_telemetry import RunTelemetry, RunTelemetryCollector, ComponentTiming
from tslab.web.series_meta import PROTECTED_TAG


class RunReportPdfTests(unittest.TestCase):
    def test_write_pdf_prep_and_final_titles(self) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        telemetry = RunTelemetry(
            run_type="Korrelation",
            started_at=now,
            output_dir="test_run",
            components=[
                ComponentTiming("job", 123.4, started_at=now, ended_at=now),
            ],
            warnings=["Test-Warnung"],
            errors=[],
            langfuse={"configured": False, "note": "inaktiv"},
            links={"Output": "/output/browse/test"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            prep = Path(tmp) / "prep_laufbericht.pdf"
            final = Path(tmp) / "laufbericht.pdf"
            write_run_report_pdf(prep, telemetry, variant="prep")
            write_run_report_pdf(final, telemetry, variant="final")
            self.assertTrue(prep.is_file())
            self.assertTrue(final.is_file())
            self.assertGreater(prep.stat().st_size, 500)
            self.assertIn(b"Prep-Laufbericht", prep.read_bytes())
            self.assertIn(b"Laufbericht", final.read_bytes())

    def test_write_pdf(self) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        telemetry = RunTelemetry(
            run_type="Korrelation",
            started_at=now,
            output_dir="test_run",
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
            root = Path(tmp)
            with patch("tslab.services.output_paths.resolve_output_dir", return_value=root):
                out = root / "run_out"
                out.mkdir()
                (out / "summary.txt").write_text("test", encoding="utf-8")
                collector = RunTelemetryCollector(run_type="Test")
                with collector.track("step_a"):
                    pass
                collector.set_output("run_out")
                prep = collector.write_pdf(variant="prep")
                final = collector.write_pdf(variant="final")
                self.assertTrue(prep["ok"])
                self.assertTrue(final["ok"])
                self.assertTrue((out / "Reports" / "prep_laufbericht.pdf").is_file())
                self.assertTrue((out / "Reports" / "laufbericht.pdf").is_file())
                self.assertEqual(collector.data.output_dir, "run_out")


class ProtectedTagConstantTests(unittest.TestCase):
    def test_protected_tag_name(self) -> None:
        self.assertEqual(PROTECTED_TAG, "Reporting")


if __name__ == "__main__":
    unittest.main()
