"""Tests fuer Kreuzkorrelation (positionsbasiert, kein Datum-Join)."""

from __future__ import annotations

import unittest

import pandas as pd

from tslab.services.correlation import compute_cross_correlation


class CrossCorrelationTests(unittest.TestCase):
    def test_lag_pairs_are_not_symmetric_when_series_differ(self) -> None:
        idx = pd.date_range("2000-01-01", periods=40, freq="MS")
        a = pd.Series([x + (x % 5) for x in range(40)], index=idx, dtype=float)
        b = pd.Series([x * 0.7 + ((x * 3) % 7) for x in range(40)], index=idx, dtype=float)

        table = compute_cross_correlation(a, b, max_lag=3)
        r1 = table.loc[table["lag"] == 1, "correlation"].iloc[0]
        rm1 = table.loc[table["lag"] == -1, "correlation"].iloc[0]

        self.assertNotAlmostEqual(r1, rm1, places=4)

    def test_positive_lag_uses_positional_shift(self) -> None:
        idx = pd.date_range("2000-01-01", periods=10, freq="MS")
        a = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], index=idx, dtype=float)
        b = pd.Series([10, 9, 8, 7, 6, 5, 4, 3, 2, 1], index=idx, dtype=float)

        table = compute_cross_correlation(a, b, max_lag=1)
        r0 = table.loc[table["lag"] == 0, "correlation"].iloc[0]
        r1 = table.loc[table["lag"] == 1, "correlation"].iloc[0]

        self.assertAlmostEqual(r0, -1.0, places=6)
        self.assertLess(r1, -0.99)


if __name__ == "__main__":
    unittest.main()
