"""Tests fuer Analysefenster und Prognose-Ende."""

from __future__ import annotations

import unittest

import pandas as pd

from tslab.services.analysis_window import resolve_study_dates


class AnalysisWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        idx = pd.date_range("1959-12-01", "2007-12-01", freq="MS")
        self.series = pd.Series(range(len(idx)), index=idx, dtype=float)

    def test_tsa_allows_forecast_end_beyond_available_data(self) -> None:
        study = resolve_study_dates(
            self.series,
            mode="tsa",
            start_date="1987-12-01",
            end_date="2006-07-01",
            forecast_end="2008-07-01",
        )
        self.assertEqual(study.cutoff, pd.Timestamp("2006-07-01"))
        self.assertEqual(study.forecast_end, pd.Timestamp("2008-07-01"))
        self.assertEqual(study.available_end, pd.Timestamp("2007-12-01"))

    def test_correlation_rejects_forecast_end_beyond_data(self) -> None:
        with self.assertRaises(ValueError):
            resolve_study_dates(
                self.series,
                mode="correlation",
                start_date="1990-01-01",
                end_date="2007-01-01",
                forecast_end="2008-07-01",
            )


if __name__ == "__main__":
    unittest.main()
