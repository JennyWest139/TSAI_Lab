"""Tests fuer Output-Namen und Order-Parsing."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from tslab.services.order_selection import parse_order_list
from tslab.services.output_naming import (
    allocate_unique_output_folder,
    correlation_folder_name,
    tsa_folder_name,
)
from tslab.services.report_naming import (
    ai_model_filename_suffix,
    corr_report_basename,
    modellvergleich_basename,
    tsa_model_folder_tag,
    tsa_model_report_basename,
)


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

    def test_allocate_unique_output_folder(self) -> None:
        parent = Path(self._get_temp_dir())
        base = "TSA_ex_xrp_close_2013-08-05_to_2026-06-14"
        self.assertEqual(allocate_unique_output_folder(parent, base), base)
        (parent / base).mkdir()
        self.assertEqual(allocate_unique_output_folder(parent, base), f"{base}_1")
        (parent / f"{base}_1").mkdir()
        self.assertEqual(allocate_unique_output_folder(parent, base), f"{base}_2")
        (parent / base).rmdir()
        (parent / f"{base}_1").rmdir()
        (parent / f"{base}_3").mkdir()
        self.assertEqual(allocate_unique_output_folder(parent, base), f"{base}_4")

    def _get_temp_dir(self) -> str:
        import tempfile

        return tempfile.mkdtemp()

    def test_tsa_model_report_names(self) -> None:
        self.assertEqual(tsa_model_folder_tag("arma11_garch11"), "ARMA11GARCH11")
        self.assertEqual(
            tsa_model_report_basename("arma11", "GPT-5-nano"),
            "TSA_Modell_Bericht_ARMA11_GPT-5-nano.docx",
        )
        self.assertEqual(
            corr_report_basename("OhneKI"),
            "CORR_AI_Bericht_OhneKI.docx",
        )
        self.assertEqual(
            modellvergleich_basename("GPT-4o-mini"),
            "Modellvergleich_GPT-4o-mini.docx",
        )
        self.assertEqual(
            ai_model_filename_suffix(model_label="GPT-4o mini"),
            "GPT-4o-mini",
        )

    def test_parse_quantiles(self) -> None:
        from tslab.services.models_garch import DEFAULT_QUANTILES, parse_quantiles

        self.assertEqual(parse_quantiles(None), DEFAULT_QUANTILES)
        self.assertEqual(parse_quantiles("0.1, 0.9"), (0.1, 0.9))


class OrderParseTests(unittest.TestCase):
    def test_single_pair(self) -> None:
        self.assertEqual(parse_order_list("1,1"), [(1, 1)])

    def test_list_pairs(self) -> None:
        self.assertEqual(parse_order_list(["2,1", "0,1"]), [(2, 1), (0, 1)])


if __name__ == "__main__":
    unittest.main()
