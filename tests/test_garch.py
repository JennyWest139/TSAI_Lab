"""Tests fuer GARCH / ARMA-GARCH."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tslab.services.models_garch import fit_arma_garch, fit_garch, forecast_garch


class GarchTests(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(42)
        idx = pd.date_range("2000-01-01", periods=200, freq="MS")
        self.y = pd.Series(rng.normal(0, 0.02, len(idx)), index=idx)

    def test_garch_fit_produces_volatility(self) -> None:
        fit = fit_garch(self.y, p=1, q=1)
        self.assertEqual(len(fit.conditional_volatility), len(self.y))
        self.assertTrue((fit.conditional_volatility > 0).all())

    def test_arma_garch_fit(self) -> None:
        fit = fit_arma_garch(self.y, arma_order=(1, 1), garch_p=1, garch_q=1)
        self.assertEqual(fit.arma_order, (1, 1))
        self.assertEqual(fit.garch.vol_order, (1, 1))

    def test_garch_forecast_quantiles(self) -> None:
        fit = fit_garch(self.y, p=1, q=1)
        idx = pd.date_range("2016-09-01", periods=3, freq="MS")
        fc = forecast_garch(fit, steps=3, index=idx)
        self.assertEqual(len(fc.mean), 3)
        self.assertIn(0.5, fc.quantiles)
        self.assertTrue((fc.quantiles[0.005] <= fc.quantiles[0.995]).all())


if __name__ == "__main__":
    unittest.main()
