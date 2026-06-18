"""Tests fuer Dezimalzahl-Erkennung beim Upload."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tslab.services.number_parse import detect_decimal_mode, parse_locale_number
from tslab.services.timeseries_store import _series_to_frame
from tslab.web.csv_preview import preview_upload_bytes


class NumberParseTests(unittest.TestCase):
    def test_detect_comma_decimal(self) -> None:
        s = pd.Series(["417,79", "1.234,56", "100"])
        self.assertEqual(detect_decimal_mode(s), "comma")

    def test_detect_dot_decimal(self) -> None:
        s = pd.Series(["1234.56", "1,234.56", "100.5"])
        self.assertEqual(detect_decimal_mode(s), "dot")

    def test_parse_dot_values(self) -> None:
        s = pd.Series(["1234.56", "99.1"])
        parsed = parse_locale_number(s, "dot")
        self.assertAlmostEqual(float(parsed.iloc[0]), 1234.56)
        self.assertAlmostEqual(float(parsed.iloc[1]), 99.1)

    def test_preview_decimal_detection(self) -> None:
        csv = "date;value\n1959-09-30;1234.56\n1959-10-31;99.10\n1959-11-30;100.25\n"
        data = preview_upload_bytes(csv.encode("utf-8"), "test.csv")
        self.assertIsNotNone(data["decimal_detection"])
        assert data["decimal_detection"] is not None
        self.assertEqual(data["decimal_detection"]["mode"], "dot")

    def test_import_frame_dot_decimal(self) -> None:
        csv = "date;value\n1959-09-30;1234.56\n1959-10-31;99.10\n"
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
                decimal_mode="dot",
            )
            self.assertEqual(len(frame), 2)
            self.assertAlmostEqual(float(frame["value"].iloc[0]), 1234.56)


if __name__ == "__main__":
    unittest.main()
