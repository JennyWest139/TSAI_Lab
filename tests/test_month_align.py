"""Tests fuer monatsweise Zeitreihen-Ausrichtung."""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from tslab.services.month_align import (
    align_monthly_pair,
    collapse_series_to_month_end,
    common_month_overlap_stamps,
    snap_to_overlap_stamp,
)


class MonthAlignTests(unittest.TestCase):
    def test_common_month_overlap_stamps_ignores_day_of_month(self) -> None:
        a = [date(2000, 1, 1), date(2000, 2, 1)]
        b = [date(2000, 1, 31), date(2000, 2, 29)]
        stamps = common_month_overlap_stamps(a, b)
        self.assertEqual(stamps, ["2000-01-01", "2000-02-01"])

    def test_align_monthly_pair(self) -> None:
        idx_a = pd.DatetimeIndex(["2000-01-01", "2000-02-01"])
        idx_b = pd.DatetimeIndex(["2000-01-31", "2000-02-29"])
        a = pd.Series([10.0, 11.0], index=idx_a)
        b = pd.Series([20.0, 21.0], index=idx_b)
        aligned_a, aligned_b = align_monthly_pair(a, b)
        self.assertEqual(len(aligned_a), 2)
        self.assertEqual(list(aligned_a.index), list(aligned_b.index))
        self.assertEqual(float(aligned_a.iloc[0]), 10.0)
        self.assertEqual(float(aligned_b.iloc[0]), 20.0)

    def test_snap_to_overlap_stamp(self) -> None:
        stamps = ["2000-01-01", "2000-02-01"]
        self.assertEqual(snap_to_overlap_stamp(stamps, "2000-01-01"), "2000-01-01")
        self.assertEqual(snap_to_overlap_stamp(stamps, "2000-01-31"), "2000-01-01")

    def test_narrower_series_window(self) -> None:
        """Kuerzere Reihe bestimmt Vorbelegung (z. B. uni vs. link)."""
        from datetime import date

        from tslab.services.month_align import compute_pair_overlap

        link_dates = [date(2020, 1, d) for d in range(1, 11)]
        uni_dates = [date(2020, 1, d) for d in range(3, 8)]
        ctx = compute_pair_overlap(
            link_dates,
            uni_dates,
            first_a=date(2020, 1, 1),
            last_a=date(2020, 1, 10),
            count_a=10,
            first_b=date(2020, 1, 3),
            last_b=date(2020, 1, 7),
            count_b=5,
            slug_a="link",
            slug_b="uni",
            label_a="Link",
            label_b="Uni",
            frequency="D",
        )
        assert ctx is not None
        self.assertEqual(ctx["narrower_series_slug"], "uni")
        self.assertEqual(ctx["suggested_start"], "2020-01-03")
        self.assertEqual(ctx["suggested_end"], "2020-01-07")
        self.assertEqual(ctx["overlap_observations"], 5)

    def test_collapse_series_to_month_end(self) -> None:
        idx = pd.DatetimeIndex(["2000-01-01", "2000-01-15", "2000-02-01"])
        s = pd.Series([1.0, 2.0, 3.0], index=idx)
        out = collapse_series_to_month_end(s)
        self.assertEqual(len(out), 2)
        self.assertEqual(out.index[-1].month, 2)


if __name__ == "__main__":
    unittest.main()
