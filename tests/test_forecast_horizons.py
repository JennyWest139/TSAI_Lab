"""Tests fuer Prognose-Horizonte und durchgehende Ist-Linie."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tslab.plots.tsa_plots import (
    _continuous_actual,
    _forecast_marker_dates,
    plot_forecast_abgleich,
)
from tslab.services.forecast_horizons import build_forecast_horizons
from tslab.services.forecast_plot_window import ForecastPlotWindow
from tslab.services.models_garch import VolatilityForecast


class ForecastHorizonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx = pd.date_range("2004-01-01", periods=48, freq="MS")
        self.prices = pd.Series(range(100, 148), index=self.idx, dtype=float)
        self.cutoff = pd.Timestamp("2006-07-01")
        self.forecast_end = pd.Timestamp("2007-07-01")
        self.window = ForecastPlotWindow(pre_years=3, forecast_years=1, post_years=1)

    def test_comparison_index_covers_overlap_and_post_year(self) -> None:
        horizons = build_forecast_horizons(
            self.prices,
            cutoff=self.cutoff,
            forecast_end=self.forecast_end,
            plot_window=self.window,
        )
        self.assertEqual(horizons.comparison_index.min(), pd.Timestamp("2006-08-01"))
        self.assertEqual(horizons.comparison_index.max(), pd.Timestamp("2007-07-01"))
        self.assertEqual(horizons.holdout_end, pd.Timestamp("2007-12-01"))

    def test_comparison_extends_to_forecast_end_beyond_data(self) -> None:
        short = self.prices.loc[: "2007-12-01"]
        horizons = build_forecast_horizons(
            short,
            cutoff=self.cutoff,
            forecast_end=pd.Timestamp("2008-07-01"),
            plot_window=self.window,
        )
        self.assertEqual(horizons.comparison_index.max(), pd.Timestamp("2008-07-01"))
        self.assertEqual(horizons.last_actual, pd.Timestamp("2007-12-01"))

    def test_forward_index_starts_after_last_actual(self) -> None:
        horizons = build_forecast_horizons(
            self.prices,
            cutoff=self.cutoff,
            forecast_end=self.forecast_end,
            plot_window=self.window,
        )
        self.assertEqual(horizons.forward_index.min(), pd.Timestamp("2007-08-01"))

    def test_continuous_actual_has_no_gap_between_train_and_holdout(self) -> None:
        train_idx = self.idx[self.idx <= self.cutoff]
        holdout_idx = self.idx[(self.idx > self.cutoff) & (self.idx <= self.forecast_end)]
        train = pd.Series(0.01, index=train_idx)
        holdout = pd.Series(0.02, index=holdout_idx)
        actual = _continuous_actual(
            train,
            holdout,
            cutoff=self.cutoff,
            plot_start=pd.Timestamp("2004-01-01"),
            plot_end=self.forecast_end,
        )
        expected = pd.concat([train, holdout]).sort_index()
        pd.testing.assert_series_equal(actual, expected)

    def test_forecast_markers_use_first_and_twelfth_value(self) -> None:
        fc_idx = pd.date_range("2006-08-01", periods=24, freq="MS")
        first, twelfth = _forecast_marker_dates(fc_idx, forecast_years=1.0)
        self.assertEqual(first, pd.Timestamp("2006-08-01"))
        self.assertEqual(twelfth, pd.Timestamp("2007-07-01"))

    def test_abgleich_plot_writes_png(self) -> None:
        train_idx = pd.date_range("2004-01-01", periods=30, freq="MS")
        fc_idx = pd.date_range("2006-08-01", periods=24, freq="MS")
        train = pd.Series(0.0, index=train_idx)
        holdout = pd.Series(0.01, index=fc_idx[:12])
        fc = VolatilityForecast(
            mean=pd.Series(0.0, index=fc_idx),
            variance=pd.Series(0.0001, index=fc_idx),
            quantiles={
                0.005: pd.Series(-0.1, index=fc_idx),
                0.05: pd.Series(-0.05, index=fc_idx),
                0.5: pd.Series(0.0, index=fc_idx),
                0.95: pd.Series(0.05, index=fc_idx),
                0.995: pd.Series(0.1, index=fc_idx),
            },
            index=fc_idx,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "abgleich.png"
            plot_forecast_abgleich(
                train,
                fc,
                holdout,
                path,
                title="Test",
                model_label="ARMA(1,1)-GARCH(1,1)",
                cutoff=pd.Timestamp("2006-07-01"),
                holdout_end=pd.Timestamp("2007-07-01"),
                plot_window=self.window,
            )
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
