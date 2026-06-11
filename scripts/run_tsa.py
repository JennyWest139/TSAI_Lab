#!/usr/bin/env python
"""
Phase 1 (TSA): ARMA, GARCH und ARMA-GARCH auf trendbereinigten log-Renditen.

Beispiele:
  python scripts/run_tsa.py --analysis-mode thesis --from-db
  python scripts/run_tsa.py --analysis-mode extended --from-db --end-date 2007-06-30
  python scripts/run_tsa.py --analysis-mode thesis --from-db --models garch,arma-garch
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.config_loader import resolve_output_dir
from tslab.db.engine import check_connection, get_session
from tslab.plots.series_display import SeriesDisplay
from tslab.plots.time_series_plots import plot_residuals, plot_series
from tslab.plots.tsa_plots import (
    plot_conditional_volatility,
    plot_forecast_quantiles,
    plot_standardized_residuals,
)
from tslab.services.analysis_mode import (
    add_analysis_mode_argument,
    get_analysis_mode_config,
    returns_display,
)
from tslab.services.models_arma import fit_arma
from tslab.services.models_garch import (
    DEFAULT_QUANTILES,
    forecast_arma_garch,
    forecast_garch,
    fit_arma_garch,
    fit_garch,
)
from tslab.services.tsa_context import load_tsa_context


def _run_arma(ctx, out: Path, p: int, q: int) -> None:
    train_lr = ctx.train_lr
    res, fitted = fit_arma(train_lr, order=(p, q))
    model_dir = out / f"arma{p}{q}"
    model_dir.mkdir(parents=True, exist_ok=True)
    display = returns_display(ctx.mode_config)

    plot_series(train_lr, model_dir / "series_train.png", display)
    plot_residuals(
        train_lr.loc[fitted.index],
        fitted,
        model_dir / f"arma{p}{q}_residuals.png",
        SeriesDisplay(
            short_name=f"Residuen nach ARMA({p},{q})",
            value_axis=f"Residuen (ARMA({p},{q}))",
            data_basis=display.data_basis,
        ),
    )

    steps = len(ctx.forecast_ctx.forecast_index)
    if steps > 0:
        from tslab.services.models_garch import VolatilityForecast

        pred = res.get_forecast(steps=steps).predicted_mean
        fc = VolatilityForecast(
            mean=pred,
            variance=pred * 0.0,
            quantiles={0.5: pred},
            index=ctx.forecast_ctx.forecast_index,
        )
        plot_forecast_quantiles(
            train_lr,
            fc,
            ctx.holdout_lr,
            model_dir / f"arma{p}{q}_forecast_holdout.png",
            title=(
                f"ARMA({p},{q}) Prognose vs. Holdout – {ctx.study.analysis_label} "
                f"[{ctx.mode_config.slug}]"
            ),
            model_label=f"ARMA({p},{q})",
        )

    summary = [
        f"Analysemodus: {ctx.mode_config.slug} ({ctx.mode_config.label_de})",
        f"Modell: ARMA({p},{q})",
        f"Analyse: {ctx.study.analysis_label}",
        f"Cutoff: {ctx.study.cutoff.date()}",
        f"Training (Renditen): {len(train_lr)}",
        f"Holdout Monate: {len(ctx.holdout_lr)}",
        "",
        str(res.summary()),
    ]
    (model_dir / "summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print(f"  ARMA({p},{q}) AIC={res.aic:.2f} -> {model_dir}")


def _run_garch(ctx, out: Path, p: int, q: int) -> None:
    train_lr = ctx.train_lr
    fit = fit_garch(train_lr, ctx.mode_config, p=p, q=q)
    model_dir = out / f"garch{p}{q}"
    model_dir.mkdir(parents=True, exist_ok=True)
    display = returns_display(ctx.mode_config)

    plot_conditional_volatility(
        fit.conditional_volatility,
        model_dir / f"garch{p}{q}_conditional_vol.png",
        display,
        title_suffix=fit.label,
    )
    plot_standardized_residuals(
        fit.standardized_residuals,
        model_dir / f"garch{p}{q}_std_residuals.png",
        display,
        title_suffix=fit.label,
    )

    steps = len(ctx.forecast_ctx.forecast_index)
    fc = forecast_garch(
        fit,
        steps=steps,
        index=ctx.forecast_ctx.forecast_index,
        quantiles=DEFAULT_QUANTILES,
    )
    if steps > 0:
        plot_forecast_quantiles(
            train_lr,
            fc,
            ctx.holdout_lr,
            model_dir / f"garch{p}{q}_forecast_quantiles.png",
            title=(
                f"{fit.label} Prognose – {ctx.study.analysis_label} "
                f"[{ctx.mode_config.slug}]"
            ),
            model_label=fit.label,
        )

    summary = [
        f"Analysemodus: {ctx.mode_config.slug} ({ctx.mode_config.label_de})",
        f"Modell: {fit.label} (mean=Zero"
        + (", Eingabe mittelwertbereinigt" if ctx.mode_config.garch_center_returns else "")
        + ")",
        f"Analyse: {ctx.study.analysis_label}",
        f"AIC: {fit.aic:.2f}",
        f"Quantile: {list(DEFAULT_QUANTILES)}",
        "",
        str(fit.result.summary()),
    ]
    (model_dir / "summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print(f"  {fit.label} AIC={fit.aic:.2f} -> {model_dir}")


def _run_arma_garch(ctx, out: Path, arma_p: int, arma_q: int, garch_p: int, garch_q: int) -> None:
    train_lr = ctx.train_lr
    fit = fit_arma_garch(
        train_lr,
        ctx.mode_config,
        arma_order=(arma_p, arma_q),
        garch_p=garch_p,
        garch_q=garch_q,
    )
    tag = f"arma{arma_p}{arma_q}_garch{garch_p}{garch_q}"
    model_dir = out / tag
    model_dir.mkdir(parents=True, exist_ok=True)
    display = returns_display(ctx.mode_config)

    if fit.joint:
        plot_standardized_residuals(
            fit.garch.standardized_residuals,
            model_dir / f"{tag}_std_residuals.png",
            display,
            title_suffix=f"{fit.label} (gemeinsam geschaetzt)",
        )
    else:
        assert fit.arma_fitted is not None
        plot_residuals(
            train_lr.loc[fit.arma_fitted.index],
            fit.arma_fitted,
            model_dir / f"{tag}_arma_residuals.png",
            SeriesDisplay(
                short_name=f"ARMA({arma_p},{arma_q}) angepasst",
                value_axis=f"ARMA({arma_p},{arma_q}) fitted",
                data_basis=display.data_basis,
            ),
        )
        plot_standardized_residuals(
            fit.garch.standardized_residuals,
            model_dir / f"{tag}_std_residuals.png",
            display,
            title_suffix=fit.label,
        )

    plot_conditional_volatility(
        fit.garch.conditional_volatility,
        model_dir / f"{tag}_conditional_vol.png",
        display,
        title_suffix=fit.label,
    )

    steps = len(ctx.forecast_ctx.forecast_index)
    fc = forecast_arma_garch(
        fit,
        steps=steps,
        index=ctx.forecast_ctx.forecast_index,
        quantiles=DEFAULT_QUANTILES,
    )
    if steps > 0:
        plot_forecast_quantiles(
            train_lr,
            fc,
            ctx.holdout_lr,
            model_dir / f"{tag}_forecast_quantiles.png",
            title=(
                f"{fit.label} Prognose – {ctx.study.analysis_label} "
                f"[{ctx.mode_config.slug}]"
            ),
            model_label=fit.label,
        )

    joint_note = "gemeinsam (arch)" if fit.joint else "zweistufig ARMA + GARCH"
    summary = [
        f"Analysemodus: {ctx.mode_config.slug} ({ctx.mode_config.label_de})",
        f"Modell: {fit.label} ({joint_note})",
        f"Analyse: {ctx.study.analysis_label}",
        f"GARCH AIC: {fit.garch.aic:.2f}",
        "",
        str(fit.garch.result.summary()),
    ]
    if not fit.joint and fit.arma_result is not None:
        summary.extend(["", "=== ARMA ===", str(fit.arma_result.summary())])
    (model_dir / "summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print(f"  {fit.label} GARCH-AIC={fit.garch.aic:.2f} -> {model_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 TSA (ARMA / GARCH / ARMA-GARCH)")
    add_analysis_mode_argument(parser, required=True)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None, help="Cutoff YYYY-MM-DD")
    parser.add_argument("--forecast-end", default=None)
    parser.add_argument("--from-db", action="store_true")
    parser.add_argument(
        "--models",
        default="arma,garch,arma-garch",
        help="Komma-Liste: arma, garch, arma-garch",
    )
    parser.add_argument("--order", default="1,1", help="ARMA(p,q) als p,q")
    parser.add_argument("--garch-order", default="1,1", help="GARCH(p,q) als p,q")
    args = parser.parse_args()

    mode_config = get_analysis_mode_config(args.analysis_mode)
    arma_p, arma_q = (int(x.strip()) for x in args.order.split(","))
    garch_p, garch_q = (int(x.strip()) for x in args.garch_order.split(","))
    models = {m.strip().lower() for m in args.models.split(",") if m.strip()}

    check_connection()
    with get_session() as session:
        ctx = load_tsa_context(
            session,
            mode_config,
            start_date=args.start_date,
            end_date=args.end_date,
            forecast_end=args.forecast_end,
        )

    out = resolve_output_dir() / f"tsa_{ctx.label}"
    out.mkdir(parents=True, exist_ok=True)

    print(f"Analysemodus: {mode_config.slug} – {mode_config.label_de}")
    print(f"TSA: {ctx.study.analysis_label}")
    print(f"Ausgabe: {out}")

    if "arma" in models:
        _run_arma(ctx, out, arma_p, arma_q)
    if "garch" in models:
        _run_garch(ctx, out, garch_p, garch_q)
    if "arma-garch" in models or "arma_garch" in models:
        _run_arma_garch(ctx, out, arma_p, arma_q, garch_p, garch_q)

    print("TSA fertig.")


if __name__ == "__main__":
    main()
