"""Tests fuer Analysemodus thesis vs. extended."""

from __future__ import annotations

import unittest

import pandas as pd

from tslab.services.analysis_mode import (
    AnalysisMode,
    get_analysis_mode_config,
    prepare_model_returns,
    resolve_study_dates_for_mode,
)


class AnalysisModeTests(unittest.TestCase):
    def test_thesis_defaults(self) -> None:
        cfg = get_analysis_mode_config(AnalysisMode.THESIS)
        start, end = resolve_study_dates_for_mode(cfg, start_date=None, end_date=None)
        self.assertEqual(start, "1987-12-01")
        self.assertEqual(end, "2007-07-01")
        self.assertFalse(cfg.returns_use_linear_detrend)
        self.assertTrue(cfg.garch_center_returns)
        self.assertTrue(cfg.arma_garch_joint)

    def test_extended_uses_detrend(self) -> None:
        cfg = get_analysis_mode_config(AnalysisMode.EXTENDED)
        idx = pd.date_range("2000-01-01", periods=24, freq="MS")
        trend = pd.Series([i * 0.01 for i in range(24)], index=idx)
        levels = (trend * 100 + 1000).rename("pdax")
        r_ext = prepare_model_returns(levels, cfg)
        self.assertAlmostEqual(float(r_ext.mean()), 0.0, places=10)


if __name__ == "__main__":
    unittest.main()
