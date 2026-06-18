"""Tests fuer TSA-Fenster-Vorschau."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from tslab.web.tsa_window_preview import build_tsa_window_preview


class TsaWindowPreviewTests(unittest.TestCase):
    @patch("tslab.web.tsa_window_preview.load_tsa_context")
    @patch("tslab.web.tsa_window_preview.load_series_full_pandas")
    def test_build_preview_regions(self, mock_load, mock_ctx) -> None:
        idx = pd.date_range("2000-01-01", periods=24, freq="MS")
        mock_load.return_value = pd.Series(range(24), index=idx, name="test")
        study = MagicMock()
        study.start_date = pd.Timestamp("2000-01-01")
        study.cutoff = pd.Timestamp("2001-06-01")
        study.forecast_end = pd.Timestamp("2002-06-01")
        study.analysis_label = "2000-01-01 bis 2001-06-01"
        study.forecast_label = "Prognose"
        ctx = MagicMock()
        ctx.study = study
        ctx.holdout_prices = pd.Series([1.0], index=pd.DatetimeIndex(["2001-07-01"]))
        ctx.horizons.forward_index = pd.date_range("2001-07-01", periods=6, freq="MS")
        mock_ctx.return_value = ctx

        session = MagicMock()
        mode_config = MagicMock()
        result = build_tsa_window_preview(
            session,
            mode_config=mode_config,
            series_slug="test",
            start_date="2000-01-01",
            end_date="2001-06-01",
            forecast_end="2002-06-01",
        )
        self.assertIn("regions", result)
        self.assertGreaterEqual(len(result["regions"]), 1)
        self.assertEqual(result["observation_count"], 24)


if __name__ == "__main__":
    unittest.main()
