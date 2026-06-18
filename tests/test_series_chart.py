"""Tests fuer interaktive Zeitreihen-Grafikdaten."""

from __future__ import annotations

import unittest

import pandas as pd

from tslab.web import mock_data as mock
from tslab.web.series_chart import build_pair_chart_payload, build_series_chart_payload


class SeriesChartTests(unittest.TestCase):
    def test_build_series_chart_payload(self) -> None:
        series = mock.mock_series_pandas("pdax")
        data = build_series_chart_payload(
            series,
            slug="pdax",
            label="PDAX",
        )
        self.assertEqual(data["slug"], "pdax")
        self.assertEqual(len(data["dates"]), len(data["values"]))
        self.assertEqual(len(data["dates"]), len(data["trend"]))
        self.assertGreater(data["observation_count"], 10)
        self.assertIn("Trendkomponente", data["trend_note"])

    def test_build_series_chart_with_returns(self) -> None:
        series = mock.mock_series_pandas("pdax")
        data = build_series_chart_payload(
            series,
            slug="pdax",
            label="PDAX",
            include_returns=True,
            analysis_mode="thesis",
        )
        self.assertIsNotNone(data["returns"])
        self.assertGreater(len(data["returns"]["dates"]), 0)

    def test_build_pair_chart_payload(self) -> None:
        a = mock.mock_series_pandas("pdax")
        b = mock.mock_series_pandas("erwerbslose")
        overlap = mock.pair_overlap("pdax", "erwerbslose")
        assert overlap is not None
        data = build_pair_chart_payload(
            a,
            b,
            slug_a="pdax",
            slug_b="erwerbslose",
            label_a="PDAX",
            label_b="Erwerbslose",
            start=overlap["overlap_start"],
            end=overlap["overlap_end"],
        )
        self.assertIn("series_a", data)
        self.assertIn("series_b", data)
        self.assertEqual(len(data["series_a"]["values"]), len(data["series_a"]["dates"]))
        self.assertEqual(data["series_a"]["dates"], data["series_b"]["dates"])
        self.assertTrue(data["returns_recommended"])

    def test_returns_recommended_for_rates(self) -> None:
        series = mock.mock_series_pandas("erwerbslose")
        data = build_series_chart_payload(
            series,
            slug="erwerbslose",
            label="Erwerbslose",
        )
        self.assertFalse(data["returns_recommended"])

    def test_month_end_dates(self) -> None:
        """Monatsend-Daten (typisch beim Upload) duerfen Grafik nicht blockieren."""
        from datetime import date

        dates = [
            date(1991, 1, 31),
            date(1991, 2, 28),
            date(1991, 3, 31),
            date(1991, 4, 30),
            date(1991, 5, 31),
            date(1991, 6, 30),
            date(1991, 7, 31),
            date(1991, 8, 31),
            date(1991, 9, 30),
            date(1991, 10, 31),
            date(1991, 11, 30),
            date(1991, 12, 31),
        ]
        idx = pd.DatetimeIndex(dates)
        series = pd.Series(range(12), index=idx, dtype=float, name="upload_test")
        data = build_series_chart_payload(
            series,
            slug="upload_test",
            label="Upload Test",
        )
        self.assertEqual(len(data["dates"]), 12)
        self.assertEqual(len(data["values"]), 12)
        self.assertIn("Trendkomponente", data["trend_note"])

    def test_slice_window(self) -> None:
        series = mock.mock_series_pandas("dax")
        idx = pd.DatetimeIndex(series.index)
        start = idx[10].date().isoformat()
        end = idx[20].date().isoformat()
        data = build_series_chart_payload(
            series,
            slug="dax",
            label="DAX",
            start=start,
            end=end,
        )
        self.assertEqual(len(data["dates"]), 11)


if __name__ == "__main__":
    unittest.main()
