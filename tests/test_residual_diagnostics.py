"""Tests fuer Residuen-Diagnostik."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from tslab.plots.series_display import SeriesDisplay
from tslab.services.residual_diagnostics import (
    compute_residual_diagnostics,
    format_residual_diagnostics,
    max_abs_acf,
    run_residual_diagnostics,
)


class ResidualDiagnosticsTests(unittest.TestCase):
    def _white_noise(self, n: int = 200, seed: int = 42) -> pd.Series:
        rng = np.random.default_rng(seed)
        idx = pd.date_range("2000-01-01", periods=n, freq="MS")
        return pd.Series(rng.normal(0, 1, size=n), index=idx, name="eps")

    def test_white_noise_ljung_box_not_rejected_at_5pct(self) -> None:
        resid = self._white_noise()
        results = compute_residual_diagnostics(resid, ljung_lags=8)
        self.assertGreaterEqual(results.ljung_box_min_p, 0.05)
        self.assertTrue(results.passes_ljung_box_5pct)

    def test_ar1_residuals_have_higher_acf_than_white_noise(self) -> None:
        rng = np.random.default_rng(7)
        n = 250
        eps = rng.normal(0, 1, size=n)
        y = np.zeros(n)
        for t in range(1, n):
            y[t] = 0.85 * y[t - 1] + eps[t]
        idx = pd.date_range("1990-01-01", periods=n, freq="MS")
        series = pd.Series(y, index=idx)
        resid = series - series.mean()

        ar_acf = max_abs_acf(resid, lags=6)
        wn_acf = max_abs_acf(self._white_noise(n=n, seed=99), lags=6)
        self.assertGreater(ar_acf, wn_acf)

    def test_format_contains_ljung_box_and_jarque_bera(self) -> None:
        results = compute_residual_diagnostics(self._white_noise())
        text = format_residual_diagnostics(results, model_label="ARMA(1,1)")
        self.assertIn("Ljung-Box", text)
        self.assertIn("Jarque-Bera", text)
        self.assertIn("ARMA(1,1)", text)

    def test_arch_lm_included_when_requested(self) -> None:
        results = compute_residual_diagnostics(
            self._white_noise(), include_arch=True, arch_lags=4
        )
        self.assertIsNotNone(results.arch_lm_stat)
        self.assertIsNotNone(results.arch_lm_p)
        text = format_residual_diagnostics(results, model_label="GARCH(1,1)")
        self.assertIn("ARCH-LM", text)

    def test_run_writes_diagnostics_files(self) -> None:
        display = SeriesDisplay(
            short_name="Test-Residuen",
            value_axis="epsilon",
            data_basis="synthetisch",
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            run_residual_diagnostics(
                self._white_noise(),
                out,
                "test_model",
                display,
                model_label="Test",
            )
            self.assertTrue((out / "test_model_diagnostics.txt").is_file())
            self.assertTrue((out / "test_model_residuals_acf.png").is_file())
            self.assertTrue((out / "test_model_residuals_qq.png").is_file())


if __name__ == "__main__":
    unittest.main()
