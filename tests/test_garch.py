"""Tests fuer GARCH / ARMA-GARCH."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tslab.services.analysis_mode import AnalysisMode, get_analysis_mode_config
from tslab.services.models_garch import fit_arma_garch, fit_garch, forecast_garch


class GarchTests(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(42)
        idx = pd.date_range("2000-01-01", periods=200, freq="MS")
        self.y = pd.Series(rng.normal(0, 0.02, len(idx)), index=idx)
        self.extended = get_analysis_mode_config(AnalysisMode.EXTENDED)
        self.thesis = get_analysis_mode_config(AnalysisMode.THESIS)

    def test_garch_fit_produces_volatility(self) -> None:
        fit = fit_garch(self.y, self.extended, p=1, q=1)
        self.assertEqual(len(fit.conditional_volatility), len(self.y))
        self.assertTrue((fit.conditional_volatility > 0).all())

    def test_thesis_garch_centers_returns(self) -> None:
        shifted = self.y + 0.01
        fit = fit_garch(shifted, self.thesis, p=1, q=1)
        self.assertAlmostEqual(fit.mean_offset, float(shifted.mean()), places=6)

    def test_arma_garch_extended_two_step(self) -> None:
        fit = fit_arma_garch(self.y, self.extended, arma_order=(1, 1), garch_p=1, garch_q=1)
        self.assertFalse(fit.joint)
        self.assertIsNotNone(fit.arma_fitted)

    def test_arma_garch_thesis_joint(self) -> None:
        fit = fit_arma_garch(self.y, self.thesis, arma_order=(1, 1), garch_p=1, garch_q=1)
        self.assertTrue(fit.joint)
        self.assertIsNotNone(fit.arch_result)

    def test_garch_forecast_quantiles(self) -> None:
        fit = fit_garch(self.y, self.extended, p=1, q=1)
        idx = pd.date_range("2016-09-01", periods=3, freq="MS")
        fc = forecast_garch(fit, steps=3, index=idx)
        self.assertEqual(len(fc.mean), 3)
        self.assertIn(0.5, fc.quantiles)


if __name__ == "__main__":
    unittest.main()
