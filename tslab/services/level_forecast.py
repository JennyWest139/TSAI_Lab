"""Ruecktransformation von Prognose-Renditen auf PDAX-Niveau."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from tslab.services.output_tables import write_dataframe_excel

from tslab.services.analysis_mode import AnalysisModeConfig
from tslab.services.models_garch import VolatilityForecast
from tslab.services.transforms import log_returns


@dataclass(frozen=True)
class LevelForecast:
    """Prognose im Originalniveau (PDAX-Kurs)."""

    mean: pd.Series
    quantiles: dict[float, pd.Series]
    index: pd.DatetimeIndex
    anchor_price: float
    anchor_date: pd.Timestamp

    def as_volatility_forecast(self) -> VolatilityForecast:
        """Fuer bestehende Plot-Hilfsfunktionen (ohne Varianz)."""
        empty_var = pd.Series(dtype=float)
        return VolatilityForecast(
            mean=self.mean,
            variance=empty_var,
            quantiles=self.quantiles,
            index=self.index,
        )


def returns_path_to_levels(
    returns: pd.Series,
    anchor_price: float,
) -> pd.Series:
    """P_t = P_0 * exp(kumulierte log-Renditen); Index = Prognosemonate."""
    clean = returns.dropna().astype(float)
    if clean.empty:
        return pd.Series(dtype=float, name="pdax_level")
    levels = float(anchor_price) * np.exp(clean.cumsum())
    return pd.Series(levels, index=clean.index, name="pdax_level")


def extrapolate_return_trend(
    train_prices: pd.Series,
    forecast_index: pd.DatetimeIndex,
) -> pd.Series:
    """Linearen Rendite-Trend fuer extended-Modus in die Zukunft verlaengern."""
    raw = log_returns(train_prices)
    if raw.empty or len(forecast_index) == 0:
        return pd.Series(dtype=float, index=forecast_index, name="return_trend")
    t = np.arange(len(raw), dtype=float)
    slope, intercept, _, _, _ = stats.linregress(t, raw.values)
    n = len(raw)
    future_t = np.arange(n, n + len(forecast_index), dtype=float)
    return pd.Series(
        intercept + slope * future_t,
        index=forecast_index,
        name="return_trend",
    )


def model_returns_to_forecast_returns(
    returns: pd.Series,
    *,
    mode_config: AnalysisModeConfig,
    train_prices: pd.Series,
    forecast_index: pd.DatetimeIndex,
) -> pd.Series:
    """Extended: linearen Trend wieder addieren; thesis: unveraendert."""
    if not mode_config.returns_use_linear_detrend:
        return returns
    trend = extrapolate_return_trend(train_prices, forecast_index)
    aligned = returns.reindex(forecast_index)
    return (aligned + trend).rename("log_returns_forecast")


def volatility_forecast_to_levels(
    forecast: VolatilityForecast,
    *,
    anchor_price: float,
    anchor_date: pd.Timestamp,
    mode_config: AnalysisModeConfig,
    train_prices: pd.Series,
) -> LevelForecast:
    """Rendite-Prognose (Mittelwert + Quantile) auf PDAX-Niveau zurueckfuehren."""
    idx = forecast.index

    def _one(series: pd.Series) -> pd.Series:
        adj = model_returns_to_forecast_returns(
            series,
            mode_config=mode_config,
            train_prices=train_prices,
            forecast_index=idx,
        )
        return returns_path_to_levels(adj, anchor_price)

    mean_levels = _one(forecast.mean) if not forecast.mean.empty else pd.Series(dtype=float)
    q_levels = {q: _one(s) for q, s in forecast.quantiles.items() if not s.empty}
    return LevelForecast(
        mean=mean_levels,
        quantiles=q_levels,
        index=idx,
        anchor_price=float(anchor_price),
        anchor_date=pd.Timestamp(anchor_date),
    )


def write_level_forecast_table(
    level_fc: LevelForecast,
    path: Path,
    *,
    holdout_prices: pd.Series | None = None,
) -> Path:
    """Excel: Datum, Punktprognose, Quantile, optional Ist-Niveau."""
    path.parent.mkdir(parents=True, exist_ok=True)
    idx = pd.DatetimeIndex(pd.to_datetime(level_fc.index)).normalize()
    rows: dict[str, object] = {
        "date": idx.strftime("%Y-%m-%d"),
        "prognose_mittelwert": level_fc.mean.reindex(idx).to_numpy(),
    }
    for q, series in sorted(level_fc.quantiles.items()):
        label = f"quantil_{q:g}".replace(".", "_")
        rows[label] = series.reindex(idx).to_numpy()
    if holdout_prices is not None and not holdout_prices.empty:
        rows["ist_pdax"] = holdout_prices.reindex(idx).to_numpy()
    df = pd.DataFrame(rows)
    return write_dataframe_excel(df, path, sheet_name="Prognose")


def format_level_forecast_summary(level_fc: LevelForecast) -> str:
    """Kurztext fuer summary.txt."""
    lines = [
        "Prognose PDAX-Niveau (Ruecktransformation aus log-Renditen)",
        f"Anker: {level_fc.anchor_date.date()}, PDAX = {level_fc.anchor_price:.2f}",
        "",
        "Datum          Mittelwert    q0.5%     q5%      q50%     q95%    q99.5%",
    ]
    q_keys = [0.005, 0.05, 0.5, 0.95, 0.995]
    for dt in level_fc.index:
        parts = [f"{pd.Timestamp(dt).date()}", f"{level_fc.mean.loc[dt]:10.2f}"]
        for q in q_keys:
            val = level_fc.quantiles.get(q, pd.Series(dtype=float))
            parts.append(
                f"{val.loc[dt]:8.2f}" if dt in val.index and not pd.isna(val.loc[dt]) else "      —"
            )
        lines.append("  ".join(parts))
    return "\n".join(lines)
