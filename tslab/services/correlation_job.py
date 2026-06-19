"""Kreuzkorrelation ausfuehren, Artefakte schreiben, Historie speichern."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from tslab.config_loader import resolve_output_dir
from tslab.db.models import CorrelationHistory
from tslab.plots.correlation_plots import plot_aligned_series, plot_cross_correlation_bars
from tslab.services.analysis_mode import AnalysisModeConfig
from tslab.services.correlation import (
    CorrelationResult,
    load_pair_for_correlation,
    run_correlation,
)
from tslab.services.output_naming import correlation_folder_name


@dataclass(frozen=True)
class CorrelationJobResult:
    result: CorrelationResult
    output_dir: Path
    best_lag: int | None
    best_r: float | None
    history_id: int | None


def _best_correlation(result: CorrelationResult) -> tuple[int | None, float | None]:
    if result.best_lag is None:
        return None, None
    best_r = float(
        result.table.loc[result.table["lag"] == result.best_lag, "correlation"].iloc[0]
    )
    return result.best_lag, best_r


def _write_summary(
    result: CorrelationResult,
    mode_config: AnalysisModeConfig,
    max_lag: int,
    path: Path,
) -> None:
    summary_lines = [
        f"Analysemodus: {mode_config.slug} ({mode_config.label_de})",
        f"Datenbasis: {result.data_basis}",
        f"Serie A: {result.series_a}",
        f"Serie B: {result.series_b}",
        f"Analysefenster: {result.study.analysis_label}",
        f"Gemeinsame Beobachtungen: {result.aligned_observations}",
        f"Lags: -{max_lag} .. +{max_lag}",
        result.lag_definition,
        "",
        "Top 5 |Korrelation|:",
    ]
    top = (
        result.table.dropna(subset=["correlation"])
        .assign(abs_r=lambda d: d["correlation"].abs())
        .sort_values("abs_r", ascending=False)
        .head(5)
    )
    for _, row in top.iterrows():
        summary_lines.append(
            f"  lag={int(row['lag']):4d}  r={row['correlation']:+.4f}  n={int(row['n_obs'])}"
        )
    best_lag, best_r = _best_correlation(result)
    if best_lag is not None and best_r is not None:
        summary_lines.append(f"\nStaerkstes |r|: lag={best_lag}, r={best_r:+.4f}")

    path.write_text("\n".join(summary_lines), encoding="utf-8")


def run_correlation_job(
    session: Session,
    series_a: str,
    series_b: str,
    *,
    mode_config: AnalysisModeConfig,
    start_date: str | None = None,
    end_date: str | None = None,
    max_lag: int = 24,
    output_root: Path | None = None,
    save_history: bool = True,
    run_name: str | None = None,
    frequency: str = "MS",
) -> CorrelationJobResult:
    """Fuehrt Korrelation aus, schreibt Output und optional DB-Historie."""
    result = run_correlation(
        session,
        series_a,
        series_b,
        mode_config=mode_config,
        start_date=start_date,
        end_date=end_date,
        max_lag=max_lag,
        frequency=frequency,
    )

    label = correlation_folder_name(
        mode_slug=mode_config.slug,
        series_a=result.series_a,
        series_b=result.series_b,
        start_date=result.study.start_date.date(),
        end_date=result.study.end_date.date(),
    )
    out = (output_root or resolve_output_dir()) / label
    out.mkdir(parents=True, exist_ok=True)

    result.table.to_csv(out / "lag_correlations.csv", index=False, encoding="utf-8-sig")
    plot_cross_correlation_bars(result, out / "cross_correlation.png")
    levels_a, levels_b, _ = load_pair_for_correlation(
        session,
        series_a,
        series_b,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
    )
    plot_aligned_series(
        result,
        levels_a,
        levels_b,
        out / "aligned_series.png",
    )
    _write_summary(result, mode_config, max_lag, out / "summary.txt")

    best_lag, best_r = _best_correlation(result)
    history_id: int | None = None
    if save_history:
        row = CorrelationHistory(
            series_a_slug=result.series_a,
            series_b_slug=result.series_b,
            start_date=result.study.start_date.date(),
            end_date=result.study.end_date.date(),
            max_lag=max_lag,
            aligned_observations=result.aligned_observations,
            best_lag=best_lag,
            best_correlation=best_r,
            analysis_mode=mode_config.slug,
            run_name=run_name,
            output_dir=str(out),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        history_id = row.id

    return CorrelationJobResult(
        result=result,
        output_dir=out,
        best_lag=best_lag,
        best_r=best_r,
        history_id=history_id,
    )
