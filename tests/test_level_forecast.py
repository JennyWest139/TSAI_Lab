"""Tests fuer Ruecktransformation Prognose -> PDAX-Niveau."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from tslab.services.analysis_mode import AnalysisMode, get_analysis_mode_config
from tslab.services.level_forecast import (
    returns_path_to_levels,
    volatility_forecast_to_levels,
    write_level_forecast_table,
)
from tslab.services.models_garch import VolatilityForecast


class LevelForecastTests(unittest.TestCase):
    def test_returns_path_to_levels(self) -> None:
        idx = pd.date_range("2000-02-01", periods=2, freq="MS")
        returns = pd.Series([0.01, 0.01], index=idx)
        levels = returns_path_to_levels(returns, 1000.0)
        self.assertAlmostEqual(levels.iloc[0], 1000.0 * np.exp(0.01), places=4)
        self.assertAlmostEqual(levels.iloc[1], 1000.0 * np.exp(0.02), places=4)

    def test_volatility_forecast_to_levels_thesis(self) -> None:
        idx = pd.date_range("2006-08-01", periods=3, freq="MS")
        fc = VolatilityForecast(
            mean=pd.Series([0.01, 0.0, -0.01], index=idx),
            variance=pd.Series(0.0001, index=idx),
            quantiles={0.5: pd.Series([0.01, 0.0, -0.01], index=idx)},
            index=idx,
        )
        prices = pd.Series(
            [1000, 1010, 1020],
            index=pd.date_range("2006-05-01", periods=3, freq="MS"),
        )
        thesis = get_analysis_mode_config(AnalysisMode.THESIS)
        level_fc = volatility_forecast_to_levels(
            fc,
            anchor_price=1020.0,
            anchor_date=pd.Timestamp("2006-07-01"),
            mode_config=thesis,
            train_prices=prices,
        )
        self.assertAlmostEqual(level_fc.mean.iloc[0], 1020.0 * np.exp(0.01), places=4)

    def test_write_level_csv(self) -> None:
        idx = pd.date_range("2006-08-01", periods=2, freq="MS")
        from tslab.services.level_forecast import LevelForecast

        level_fc = LevelForecast(
            mean=pd.Series([1100.0, 1120.0], index=idx),
            quantiles={0.5: pd.Series([1100.0, 1120.0], index=idx)},
            index=idx,
            anchor_price=1000.0,
            anchor_date=pd.Timestamp("2006-07-01"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "levels.csv"
            write_level_forecast_table(level_fc, path)
            self.assertTrue(path.is_file())
            text = path.read_text(encoding="utf-8-sig")
            self.assertIn("prognose_mittelwert", text)


if __name__ == "__main__":
    unittest.main()
