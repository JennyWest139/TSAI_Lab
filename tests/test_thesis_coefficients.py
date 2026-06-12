"""Tests fuer Koeffizienten-Abgleich mit Diplomarbeit."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import pandas as pd

from tslab.services.thesis_coefficients import (
    _within_tolerance,
    compare_parameters,
    extract_arma_params_r_style,
    load_thesis_reference,
)


class ThesisCoefficientTests(unittest.TestCase):
    def test_reference_yaml_loads(self) -> None:
        ref = load_thesis_reference()
        self.assertIn("arma11", ref["models"])
        self.assertEqual(ref["study"]["start_date"], "1987-12-01")

    def test_arma_r_style_sign_mapping(self) -> None:
        res = SimpleNamespace(
            params=pd.Series(
                {
                    "const": 0.00783,
                    "ar.L1": 0.85124,
                    "ma.L1": -0.82949,
                    "sigma2": 0.00408,
                }
            ),
            aic=-586.19,
            nobs=223,
        )
        mapped = extract_arma_params_r_style(res)
        self.assertAlmostEqual(mapped["ar1"], -0.85124, places=5)
        self.assertAlmostEqual(mapped["ma1"], 0.82949, places=5)
        self.assertAlmostEqual(mapped["intercept"], 0.00783, places=5)

    def test_compare_flags_large_garch_alpha_diff(self) -> None:
        ref = load_thesis_reference()
        rows = compare_parameters(
            "garch11",
            ref["models"]["garch11"],
            {
                "mu": 0.0,
                "omega": 0.00041,
                "alpha1": 0.21,
                "beta1": 0.72,
            },
        )
        alpha_row = next(r for r in rows if r.parameter == "alpha1")
        self.assertEqual(alpha_row.status, "diff")

    def test_within_tolerance_relative(self) -> None:
        self.assertTrue(_within_tolerance(0.9, 0.85, abs_tol=0.01, rel_tol=0.1))
        self.assertFalse(_within_tolerance(0.1, 0.21, abs_tol=0.01, rel_tol=0.1))


if __name__ == "__main__":
    unittest.main()
