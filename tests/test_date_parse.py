"""Tests fuer flexible Datumserkennung beim Upload."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tslab.services.date_parse import analyze_date_column, detect_date_format, parse_observation_dates
from tslab.services.timeseries_store import _series_to_frame
from tslab.web.csv_preview import preview_upload_bytes


class DateParseTests(unittest.TestCase):
    def test_detect_iso_format(self) -> None:
        s = pd.Series(["1959-09-30", "1959-10-31", "1959-11-30"])
        det = detect_date_format(s)
        self.assertEqual(det.mode, "iso")
        self.assertGreaterEqual(det.parse_rate, 0.99)
        self.assertEqual(det.samples[0]["parsed"], "1959-09-30")

    def test_detect_german_dot_format(self) -> None:
        s = pd.Series(["30.09.1959", "31.10.1959", "30.11.1959"])
        det = detect_date_format(s)
        self.assertEqual(det.mode, "dmy_dot")
        self.assertGreaterEqual(det.parse_rate, 0.99)

    def test_parse_iso_series(self) -> None:
        s = pd.Series(["1959-09-30", "1959-10-31"])
        parsed = parse_observation_dates(s, mode="iso")
        self.assertEqual(parsed.iloc[0].date().isoformat(), "1959-09-30")

    def test_preview_iso_csv(self) -> None:
        csv = "date;value\n1959-09-30;100\n1959-10-31;101\n"
        data = preview_upload_bytes(csv.encode("utf-8"), "test.csv")
        self.assertEqual(data["suggested_date_column"], "date")
        self.assertIsNotNone(data["date_detection"])
        assert data["date_detection"] is not None
        self.assertEqual(data["date_detection"]["mode"], "iso")

    def test_import_frame_iso(self) -> None:
        csv = "date;value\n1959-09-30;100,5\n1959-10-31;101,2\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.csv"
            path.write_text(csv, encoding="utf-8")
            frame = _series_to_frame(
                path,
                "date",
                "value",
                date_parse_mode="iso",
                sep=";",
                encoding="utf-8",
            )
            self.assertEqual(len(frame), 2)
            self.assertEqual(frame["obs_date"].iloc[0].date().isoformat(), "1959-09-30")


if __name__ == "__main__":
    unittest.main()
