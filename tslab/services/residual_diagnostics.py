"""Residuen-Diagnostik: Tests und Ausgabe (Ljung-Box, Normalitaet, ARCH-LM)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import jarque_bera
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.tsa.stattools import acf as sm_acf

from tslab.plots.residual_diagnostics_plots import (
    export_residual_diagnostic_plots,
    plot_model_decomposition,
)
from tslab.plots.series_display import SeriesDisplay


@dataclass(frozen=True)
class LjungBoxRow:
    lag: int
    statistic: float
    p_value: float


@dataclass(frozen=True)
class ResidualDiagnosticResults:
    n: int
    mean: float
    std: float
    ljung_box: tuple[LjungBoxRow, ...]
    jarque_bera_stat: float
    jarque_bera_p: float
    arch_lm_stat: float | None = None
    arch_lm_p: float | None = None
    arch_lags: int | None = None

    @property
    def ljung_box_min_p(self) -> float:
        if not self.ljung_box:
            return float("nan")
        return min(row.p_value for row in self.ljung_box)

    @property
    def passes_ljung_box_5pct(self) -> bool:
        return self.ljung_box_min_p >= 0.05

    @property
    def passes_jarque_bera_5pct(self) -> bool:
        return self.jarque_bera_p >= 0.05

    @property
    def passes_arch_lm_5pct(self) -> bool:
        if self.arch_lm_p is None:
            return True
        return self.arch_lm_p >= 0.05


def _clean_residuals(residuals: pd.Series) -> pd.Series:
    clean = residuals.dropna().astype(float)
    if clean.empty:
        raise ValueError("Residuen sind leer.")
    return clean


def compute_residual_diagnostics(
    residuals: pd.Series,
    *,
    ljung_lags: int = 12,
    arch_lags: int = 12,
    include_arch: bool = False,
) -> ResidualDiagnosticResults:
    """Ljung-Box, Jarque-Bera und optional ARCH-LM auf Residuen."""
    clean = _clean_residuals(residuals)
    n = len(clean)
    max_lb_lag = max(1, min(ljung_lags, n // 2 - 1))

    lb = acorr_ljungbox(clean, lags=list(range(1, max_lb_lag + 1)), return_df=True)
    lb_rows = tuple(
        LjungBoxRow(
            lag=int(lag),
            statistic=float(lb.loc[lag, "lb_stat"]),
            p_value=float(lb.loc[lag, "lb_pvalue"]),
        )
        for lag in lb.index
    )

    jb_stat, jb_p = jarque_bera(clean.values)

    arch_stat: float | None = None
    arch_p: float | None = None
    eff_arch_lags: int | None = None
    if include_arch:
        eff_arch_lags = max(1, min(arch_lags, n // 4))
        lm_stat, lm_pvalue, _, _ = het_arch(clean.values, nlags=eff_arch_lags)
        arch_stat = float(lm_stat)
        arch_p = float(lm_pvalue)

    return ResidualDiagnosticResults(
        n=n,
        mean=float(clean.mean()),
        std=float(clean.std(ddof=1)),
        ljung_box=lb_rows,
        jarque_bera_stat=float(jb_stat),
        jarque_bera_p=float(jb_p),
        arch_lm_stat=arch_stat,
        arch_lm_p=arch_p,
        arch_lags=eff_arch_lags,
    )


def format_residual_diagnostics(
    results: ResidualDiagnosticResults,
    *,
    model_label: str,
    residual_label: str = "Residuen",
) -> str:
    """Textzusammenfassung fuer diagnostics.txt / summary.txt."""
    lines = [
        f"Residuen-Diagnostik: {model_label}",
        f"Serie: {residual_label}",
        f"n = {results.n}, Mittelwert = {results.mean:.6f}, Std = {results.std:.6f}",
        "",
        "Ljung-Box (H0: keine Autokorrelation):",
    ]
    for row in results.ljung_box:
        flag = "ok" if row.p_value >= 0.05 else "signifikant"
        lines.append(
            f"  Lag {row.lag:2d}: Q = {row.statistic:8.3f}, p = {row.p_value:.4f} ({flag})"
        )
    lines.extend(
        [
            f"  -> kleinster p-Wert: {results.ljung_box_min_p:.4f}",
            "",
            f"Jarque-Bera (H0: Normalverteilung): "
            f"JB = {results.jarque_bera_stat:.3f}, p = {results.jarque_bera_p:.4f}",
        ]
    )
    if results.arch_lm_stat is not None and results.arch_lags is not None:
        arch_flag = "ok" if results.arch_lm_p and results.arch_lm_p >= 0.05 else "signifikant"
        lines.extend(
            [
                "",
                f"ARCH-LM auf quadrierten Residuen (Lags={results.arch_lags}, "
                f"H0: keine ARCH-Effekte):",
                f"  LM = {results.arch_lm_stat:.3f}, p = {results.arch_lm_p:.4f} ({arch_flag})",
            ]
        )

    lines.extend(
        [
            "",
            "Interpretation (alpha = 5 %):",
            f"  Keine verbleibende Autokorrelation: "
            f"{'ja' if results.passes_ljung_box_5pct else 'nein (pruefen)'}",
            f"  Normalitaet der Residuen: "
            f"{'nicht verworfen' if results.passes_jarque_bera_5pct else 'verworfen'}",
        ]
    )
    if results.arch_lm_p is not None:
        lines.append(
            f"  Keine verbleibende Heteroskedastizitaet (ARCH-LM): "
            f"{'ja' if results.passes_arch_lm_5pct else 'nein (pruefen)'}"
        )
    return "\n".join(lines)


def max_abs_acf(residuals: pd.Series, lags: int = 12) -> float:
    """Hilfe fuer Tests: max. |ACF| der Residuen (ohne Lag 0)."""
    clean = _clean_residuals(residuals)
    max_lag = max(1, min(lags, len(clean) // 2 - 1))
    values = sm_acf(clean, nlags=max_lag, fft=True)
    if len(values) <= 1:
        return 0.0
    return float(np.max(np.abs(values[1:])))


def run_residual_diagnostics(
    residuals: pd.Series,
    out_dir: Path,
    file_tag: str,
    display: SeriesDisplay,
    *,
    model_label: str,
    include_arch: bool = False,
    ljung_lags: int = 12,
    arch_lags: int = 12,
    acf_lags: int = 24,
) -> ResidualDiagnosticResults:
    """Tests berechnen, Text + Diagnose-Plots schreiben."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = compute_residual_diagnostics(
        residuals,
        ljung_lags=ljung_lags,
        arch_lags=arch_lags,
        include_arch=include_arch,
    )
    export_residual_diagnostic_plots(
        residuals,
        out_dir,
        file_tag,
        display,
        include_arch=include_arch,
        acf_lags=acf_lags,
    )
    text = format_residual_diagnostics(
        results,
        model_label=model_label,
        residual_label=display.short_name,
    )
    (out_dir / f"{file_tag}_diagnostics.txt").write_text(text, encoding="utf-8")
    return results


def run_model_fit_diagnostics(
    y: pd.Series,
    fitted: pd.Series,
    out_dir: Path,
    file_tag: str,
    series_display: SeriesDisplay,
    residual_display: SeriesDisplay,
    *,
    model_label: str,
    include_arch: bool = False,
    ljung_lags: int = 12,
    arch_lags: int = 12,
    acf_lags: int = 24,
) -> ResidualDiagnosticResults:
    """Modellzerlegung (Beobachtet/Fitted/Residuen) plus Residuen-Diagnostik."""
    aligned_y = y.loc[fitted.index]
    resid = (aligned_y - fitted).dropna()
    plot_model_decomposition(
        aligned_y,
        fitted,
        out_dir / f"{file_tag}_decomposition.png",
        series_display,
        model_label=model_label,
    )
    return run_residual_diagnostics(
        resid,
        out_dir,
        file_tag,
        residual_display,
        model_label=model_label,
        include_arch=include_arch,
        ljung_lags=ljung_lags,
        arch_lags=arch_lags,
        acf_lags=acf_lags,
    )
