"""Tests fuer Output-Namen und Order-Parsing."""

from __future__ import annotations

import unittest
from datetime import date

from tslab.services.order_selection import parse_order_list
from tslab.services.output_naming import correlation_folder_name, tsa_folder_name


class OutputNamingTests(unittest.TestCase):
    def test_correlation_folder_thesis(self) -> None:
        name = correlation_folder_name(
            mode_slug="thesis",
            series_a="pdax",
            series_b="dax",
            start_date=date(1991, 1, 1),
            end_date=date(2007, 1, 1),
        )
        self.assertEqual(name, "CORR_th_pdax_vs_dax_1991-01-01_to_2007-01-01")

    def test_tsa_folder_extended(self) -> None:
        name = tsa_folder_name(
            mode_slug="extended",
            series_slug="pdax",
            train_start=date(1987, 12, 1),
            train_end=date(2006, 7, 1),
        )
        self.assertEqual(name, "TSA_ex_pdax_1987-12-01_to_2006-07-01")


class OrderParseTests(unittest.TestCase):
    def test_single_pair(self) -> None:
        self.assertEqual(parse_order_list("1,1"), [(1, 1)])

    def test_list_pairs(self) -> None:
        self.assertEqual(parse_order_list(["2,1", "0,1"]), [(2, 1), (0, 1)])


if __name__ == "__main__":
    unittest.main()
