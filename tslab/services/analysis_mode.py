"""Analysemodus: Diplomarbeit (thesis) vs. erweitert (extended).

Wird in CLI und spaeter in der Oberflaeche als expliziter Schalter genutzt.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum

import pandas as pd

from tslab.plots.series_display import PDAX_LOG_RETURNS, SeriesDisplay
from tslab.services.transforms import log_returns, log_returns_detrended


class AnalysisMode(str, Enum):
    """thesis = JW 2008; extended = laengere Stichprobe + lineare Detrending."""

    THESIS = "thesis"
    EXTENDED = "extended"


@dataclass(frozen=True)
class AnalysisModeConfig:
    mode: AnalysisMode
    default_start: str | None
    default_end: str | None
    returns_use_linear_detrend: bool
    garch_center_returns: bool
    arma_garch_joint: bool

    @property
    def slug(self) -> str:
        return self.mode.value

    @property
    def label_de(self) -> str:
        if self.mode is AnalysisMode.THESIS:
            return "Diplomarbeit JW 2008 (ab 12/1987, kont. Renditen ohne lineares Detrending)"
        return "Erweitert (volle Historie, lineare Trendentfernung auf Renditen)"


def parse_analysis_mode(value: str) -> AnalysisMode:
    try:
        return AnalysisMode(value.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(m.value for m in AnalysisMode)
        raise argparse.ArgumentTypeError(
            f"Ungueltiger analysis-mode '{value}'. Erlaubt: {allowed}"
        ) from exc


def get_analysis_mode_config(mode: AnalysisMode) -> AnalysisModeConfig:
    if mode is AnalysisMode.THESIS:
        return AnalysisModeConfig(
            mode=mode,
            default_start="1987-12-01",
            default_end="2007-07-01",
            returns_use_linear_detrend=False,
            garch_center_returns=True,
            arma_garch_joint=True,
        )
    return AnalysisModeConfig(
        mode=mode,
        default_start=None,
        default_end=None,
        returns_use_linear_detrend=True,
        garch_center_returns=False,
        arma_garch_joint=False,
    )


def add_analysis_mode_argument(
    parser: argparse.ArgumentParser,
    *,
    required: bool = True,
) -> None:
    parser.add_argument(
        "--analysis-mode",
        type=parse_analysis_mode,
        required=required,
        choices=[m.value for m in AnalysisMode],
        help=(
            "thesis = Diplomarbeit JW 2008 (Stichprobe ab 12/1987, kont. Renditen, "
            "GARCH auf zentrierten Renditen, gemeinsames ARMA-GARCH); "
            "extended = volle Historie + lineare Detrending auf Renditen"
        ),
    )


def resolve_study_dates_for_mode(
    mode_config: AnalysisModeConfig,
    *,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str | None, str | None]:
    """Modus-Defaults nur wenn der Nutzer kein Datum gesetzt hat."""
    eff_start = start_date if start_date is not None else mode_config.default_start
    eff_end = end_date if end_date is not None else mode_config.default_end
    return eff_start, eff_end


def prepare_model_returns(series: pd.Series, mode_config: AnalysisModeConfig) -> pd.Series:
    if mode_config.returns_use_linear_detrend:
        return log_returns_detrended(series)
    return log_returns(series)


def prepare_garch_input(
    returns: pd.Series,
    mode_config: AnalysisModeConfig,
) -> tuple[pd.Series, float]:
    """Rueckgabe: (Reihe fuer GARCH-Fit, Mittelwert fuer Prognose-Ruecktransformation)."""
    if mode_config.garch_center_returns:
        mu = float(returns.mean())
        return (returns - mu).rename(returns.name or "returns_centered"), mu
    return returns, 0.0


def returns_display(mode_config: AnalysisModeConfig) -> SeriesDisplay:
    if mode_config.mode is AnalysisMode.THESIS:
        return SeriesDisplay(
            short_name="kont. Renditen (Diplom)",
            value_axis="Transformiert: diff(ln(PDAX))",
            data_basis=(
                "Bearbeitet: erste Differenz von ln(PDAX), ohne lineare Trendentfernung "
                "(Modus: thesis / Diplomarbeit JW 2008)"
            ),
        )
    return PDAX_LOG_RETURNS
