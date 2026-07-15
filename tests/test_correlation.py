"""Tests fuer Kreuzkorrelation (positionsbasiert, kein Datum-Join)."""

from __future__ import annotations

import unittest

import pandas as pd

from tslab.services.analysis_mode import AnalysisMode, get_analysis_mode_config, returns_display
from tslab.services.correlation import (
    compute_cross_correlation,
    prepare_correlation_returns,
    resolve_correlation_study_dates,
)
from tslab.services.transforms import log_returns


class CrossCorrelationTests(unittest.TestCase):
    def test_lag_pairs_are_not_symmetric_when_series_differ(self) -> None:
        idx = pd.date_range("2000-01-01", periods=40, freq="MS")
        a = pd.Series([x + (x % 5) for x in range(40)], index=idx, dtype=float)
        b = pd.Series([x * 0.7 + ((x * 3) % 7) for x in range(40)], index=idx, dtype=float)

        table = compute_cross_correlation(a, b, max_lag=3)
        r1 = table.loc[table["lag"] == 1, "correlation"].iloc[0]
        rm1 = table.loc[table["lag"] == -1, "correlation"].iloc[0]

        self.assertNotAlmostEqual(r1, rm1, places=4)

    def test_positive_lag_uses_positional_shift(self) -> None:
        idx = pd.date_range("2000-01-01", periods=10, freq="MS")
        a = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], index=idx, dtype=float)
        b = pd.Series([10, 9, 8, 7, 6, 5, 4, 3, 2, 1], index=idx, dtype=float)

        table = compute_cross_correlation(a, b, max_lag=1)
        r0 = table.loc[table["lag"] == 0, "correlation"].iloc[0]
        r1 = table.loc[table["lag"] == 1, "correlation"].iloc[0]

        self.assertAlmostEqual(r0, -1.0, places=6)
        self.assertLess(r1, -0.99)

    def test_thesis_mode_uses_plain_log_returns(self) -> None:
        idx = pd.date_range("2000-01-01", periods=24, freq="MS")
        levels = pd.Series([1000 + i * 5 for i in range(24)], index=idx, name="pdax")
        cfg = get_analysis_mode_config(AnalysisMode.THESIS)
        a, _ = prepare_correlation_returns(levels, levels, cfg)
        expected = log_returns(levels)
        self.assertFalse(cfg.returns_use_linear_detrend)
        pd.testing.assert_series_equal(a, expected, check_names=False)

    def test_extended_mode_detrends_returns(self) -> None:
        idx = pd.date_range("2000-01-01", periods=24, freq="MS")
        levels = pd.Series([1000 + i * 5 for i in range(24)], index=idx, name="pdax")
        cfg = get_analysis_mode_config(AnalysisMode.EXTENDED)
        a, _ = prepare_correlation_returns(levels, levels, cfg)
        self.assertAlmostEqual(float(a.mean()), 0.0, places=10)

    def test_thesis_default_study_window(self) -> None:
        idx = pd.date_range("1980-01-01", "2010-01-01", freq="MS")
        a = pd.Series(1.0, index=idx)
        b = pd.Series(2.0, index=idx)
        cfg = get_analysis_mode_config(AnalysisMode.THESIS)
        start, end = cfg.default_start, cfg.default_end
        study = resolve_correlation_study_dates(a, b, start_date=start, end_date=end)
        self.assertEqual(study.start_date, pd.Timestamp("1987-12-31"))
        self.assertEqual(study.end_date, pd.Timestamp("2007-07-31"))

    def test_correlation_data_basis_is_generic_without_pdax(self) -> None:
        for mode in (AnalysisMode.THESIS, AnalysisMode.EXTENDED):
            cfg = get_analysis_mode_config(mode)
            disp = returns_display(cfg)
            self.assertNotIn("PDAX", disp.data_basis)
            self.assertIn("ln(P_t)", disp.data_basis)


if __name__ == "__main__":
    unittest.main()
