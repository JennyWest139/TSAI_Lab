"""Tests fuer Histogramm mit Normalverteilungskurve und Textumbruch."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from tslab.plots.series_display import PDAX_LOG_RETURNS
from tslab.plots.text_util import wrap_plot_text
from tslab.plots.time_series_plots import plot_histogram


class PlotEnhancementTests(unittest.TestCase):
    def test_wrap_plot_text_breaks_long_line(self) -> None:
        text = " ".join(["Wort"] * 30)
        wrapped = wrap_plot_text(text, width=20)
        self.assertIn("\n", wrapped)
        self.assertGreater(len(wrapped.split("\n")), 1)

    def test_histogram_writes_png_with_normal_curve(self) -> None:
        rng = np.random.default_rng(42)
        idx = pd.date_range("2000-01-01", periods=120, freq="MS")
        series = pd.Series(rng.normal(0, 0.02, len(idx)), index=idx)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hist.png"
            plot_histogram(series, path, PDAX_LOG_RETURNS)
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 1000)
            with Image.open(path) as im:
                self.assertEqual(im.format, "PNG")


if __name__ == "__main__":
    unittest.main()
