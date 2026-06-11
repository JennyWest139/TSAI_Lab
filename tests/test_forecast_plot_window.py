"""Tests fuer Prognose-Grafikfenster."""

from __future__ import annotations

import unittest

import pandas as pd

from tslab.services.forecast_plot_window import (
    ForecastPlotWindow,
    apply_forecast_plot_window,
    resolve_forecast_plot_bounds,
)
from tslab.services.models_garch import VolatilityForecast


class ForecastPlotWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx = pd.date_range("2000-01-01", periods=120, freq="MS")
        self.cutoff = pd.Timestamp("2009-12-01")
        self.train = pd.Series(range(96), index=self.idx[:96], dtype=float)
        self.fc_idx = pd.date_range("2010-01-01", periods=24, freq="MS")
        self.forecast = VolatilityForecast(
            mean=pd.Series(1.0, index=self.fc_idx),
            variance=pd.Series(0.01, index=self.fc_idx),
            quantiles={0.5: pd.Series(1.0, index=self.fc_idx)},
            index=self.fc_idx,
        )
        self.holdout = pd.Series(2.0, index=self.fc_idx[:12])

    def test_default_window_starts_three_years_before_cutoff(self) -> None:
        window = ForecastPlotWindow()
        start, _ = resolve_forecast_plot_bounds(
            self.cutoff, self.forecast.index, self.holdout, window
        )
        expected = self.cutoff - pd.DateOffset(months=36)
        self.assertEqual(start, expected)

    def test_default_window_shows_one_year_holdout_without_extra_forecast(self) -> None:
        window = ForecastPlotWindow()
        fc_idx = pd.date_range("2010-01-01", periods=12, freq="MS")
        fc_short = VolatilityForecast(
            mean=pd.Series(1.0, index=fc_idx),
            variance=pd.Series(0.01, index=fc_idx),
            quantiles={0.5: pd.Series(1.0, index=fc_idx)},
            index=fc_idx,
        )
        _, end = resolve_forecast_plot_bounds(
            self.cutoff, fc_short.index, self.holdout.iloc[:12], window
        )
        self.assertEqual(end, pd.Timestamp("2010-12-01"))

    def test_post_year_uses_extended_forecast_quantiles_when_available(self) -> None:
        window = ForecastPlotWindow()
        _, end = resolve_forecast_plot_bounds(
            self.cutoff, self.forecast.index, self.holdout.iloc[:12], window
        )
        self.assertEqual(end, pd.Timestamp("2011-12-01"))

    def test_train_slice_limits_history(self) -> None:
        window = ForecastPlotWindow(pre_years=3, forecast_years=1, post_years=1)
        train_p, _, _, plot_start, _ = apply_forecast_plot_window(
            self.train, self.forecast, self.holdout, self.cutoff, window
        )
        self.assertEqual(train_p.index.min(), plot_start)
        self.assertEqual(train_p.index.max(), pd.Timestamp("2007-12-01"))
        self.assertEqual(len(train_p), 13)

    def test_post_years_zero_stops_at_forecast_horizon(self) -> None:
        window = ForecastPlotWindow(pre_years=1, forecast_years=1, post_years=0)
        _, end = resolve_forecast_plot_bounds(
            self.cutoff, self.forecast.index, self.holdout, window
        )
        self.assertEqual(end, pd.Timestamp("2010-12-01"))

    def test_resolve_from_custom_values(self) -> None:
        window = ForecastPlotWindow(pre_years=2, forecast_years=0.5, post_years=0.5)
        start, end = resolve_forecast_plot_bounds(
            self.cutoff, self.forecast.index, pd.Series(dtype=float), window
        )
        self.assertEqual(start, self.cutoff - pd.DateOffset(months=24))
        self.assertEqual(end, pd.Timestamp("2010-12-01"))


if __name__ == "__main__":
    unittest.main()
