#!/usr/bin/env python
"""
Phase 1 (TSA): ARMA, GARCH und ARMA-GARCH auf trendbereinigten log-Renditen.

Beispiele:
  python scripts/run_tsa.py --analysis-mode thesis --from-db
  python scripts/run_tsa.py --analysis-mode extended --from-db --end-date 2007-06-30
  python scripts/run_tsa.py --analysis-mode thesis --from-db --models garch,arma-garch
  python scripts/run_tsa.py --analysis-mode thesis --from-db --plot-pre-years 3 --plot-forecast-years 1 --plot-post-years 1
  # Diplomarbeit-Abgleich (Training bis 07/2006, Ist+Prognose 07/2006-07/2007):
  python scripts/run_tsa.py --analysis-mode thesis --from-db --end-date 2006-07-01 --forecast-end 2008-07-01
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
from tslab.plots.tsa_plots import plot_conditional_volatility, plot_standardized_residuals
from tslab.services.forecast_plot_service import (
    arma_volatility_forecast,
    write_thesis_forecast_plots,
)
from tslab.services.analysis_mode import (
    add_analysis_mode_argument,
    get_analysis_mode_config,
    returns_display,
)
from tslab.services.models_arma import fit_arma
from tslab.services.residual_diagnostics import (
    ResidualDiagnosticResults,
    format_residual_diagnostics,
    run_model_fit_diagnostics,
    run_residual_diagnostics,
)
from tslab.services.models_garch import (
    DEFAULT_QUANTILES,
    forecast_arma_garch,
    forecast_garch,
    fit_arma_garch,
    fit_garch,
)
from tslab.services.forecast_plot_window import (
    ForecastPlotWindow,
    add_forecast_plot_window_arguments,
    forecast_plot_window_from_args,
)
from tslab.services.tsa_context import load_tsa_context


def _forecast_ylabel(ctx) -> str:
    disp = returns_display(ctx.mode_config)
    if "diff(ln(PDAX))" in disp.value_axis:
        return "kont. Renditen"
    return disp.value_axis


def _std_residual_display(display: SeriesDisplay, model_label: str) -> SeriesDisplay:
    return SeriesDisplay(
        short_name=f"Standardisierte Residuen ({model_label})",
        value_axis="z_t",
        data_basis=(
            f"Modelloutput: standardisierte Residuen aus {model_label}; "
            f"Eingabe: {display.data_basis}"
        ),
    )


def _run_arma(
    ctx, out: Path, p: int, q: int, plot_window: ForecastPlotWindow
) -> None:
    train_lr = ctx.train_lr
    res, fitted = fit_arma(train_lr, order=(p, q))
    model_dir = out / f"arma{p}{q}"
    model_dir.mkdir(parents=True, exist_ok=True)
    display = returns_display(ctx.mode_config)

    plot_series(train_lr, model_dir / "series_train.png", display)
    resid_display = SeriesDisplay(
        short_name=f"Residuen nach ARMA({p},{q})",
        value_axis=f"Residuen (ARMA({p},{q}))",
        data_basis=display.data_basis,
    )
    tag = f"arma{p}{q}"
    plot_residuals(
        train_lr.loc[fitted.index],
        fitted,
        model_dir / f"{tag}_residuals.png",
        resid_display,
    )
    diag = run_model_fit_diagnostics(
        train_lr,
        fitted,
        model_dir,
        tag,
        display,
        resid_display,
        model_label=f"ARMA({p},{q})",
    )

    model_label = f"ARMA({p},{q})"
    title_base = f"{model_label} – {ctx.study.analysis_label} [{ctx.mode_config.slug}]"

    def _fc_factory(steps: int, index) -> object:
        return arma_volatility_forecast(res, steps=steps, index=index)

    fwd_factory = None
    if not ctx.holdout_lr.empty:
        res_fwd, _ = fit_arma(ctx.forward_train_lr, order=(p, q))

        def _fwd_factory(steps: int, index) -> object:
            return arma_volatility_forecast(res_fwd, steps=steps, index=index)

        fwd_factory = _fwd_factory

    write_thesis_forecast_plots(
        train_lr=train_lr,
        holdout_lr=ctx.holdout_lr,
        horizons=ctx.horizons,
        forward_train_lr=ctx.forward_train_lr,
        forecast_factory=_fc_factory,
        forward_forecast_factory=fwd_factory,
        out_dir=model_dir,
        file_tag=tag,
        title_base=title_base,
        model_label=model_label,
        plot_window=plot_window,
        y_label=_forecast_ylabel(ctx),
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
        "",
        format_residual_diagnostics(diag, model_label=f"ARMA({p},{q})"),
    ]
    (model_dir / "summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print(f"  ARMA({p},{q}) AIC={res.aic:.2f} -> {model_dir}")


def _run_garch(
    ctx, out: Path, p: int, q: int, plot_window: ForecastPlotWindow
) -> None:
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
    tag = f"garch{p}{q}"
    std_disp = _std_residual_display(display, fit.label)
    plot_standardized_residuals(
        fit.standardized_residuals,
        model_dir / f"{tag}_std_residuals.png",
        display,
        title_suffix=fit.label,
    )
    diag = run_residual_diagnostics(
        fit.standardized_residuals,
        model_dir,
        tag,
        std_disp,
        model_label=fit.label,
        include_arch=True,
    )

    model_label = fit.label
    title_base = f"{model_label} – {ctx.study.analysis_label} [{ctx.mode_config.slug}]"

    def _fc_factory(steps: int, index) -> object:
        return forecast_garch(
            fit, steps=steps, index=index, quantiles=DEFAULT_QUANTILES
        )

    fwd_factory = None
    if not ctx.holdout_lr.empty:
        fit_fwd = fit_garch(
            ctx.forward_train_lr, ctx.mode_config, p=p, q=q
        )

        def _fwd_factory(steps: int, index) -> object:
            return forecast_garch(
                fit_fwd, steps=steps, index=index, quantiles=DEFAULT_QUANTILES
            )

        fwd_factory = _fwd_factory

    write_thesis_forecast_plots(
        train_lr=train_lr,
        holdout_lr=ctx.holdout_lr,
        horizons=ctx.horizons,
        forward_train_lr=ctx.forward_train_lr,
        forecast_factory=_fc_factory,
        forward_forecast_factory=fwd_factory,
        out_dir=model_dir,
        file_tag=tag,
        title_base=title_base,
        model_label=model_label,
        plot_window=plot_window,
        y_label=_forecast_ylabel(ctx),
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
        "",
        format_residual_diagnostics(diag, model_label=fit.label),
    ]
    (model_dir / "summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print(f"  {fit.label} AIC={fit.aic:.2f} -> {model_dir}")


def _run_arma_garch(
    ctx,
    out: Path,
    arma_p: int,
    arma_q: int,
    garch_p: int,
    garch_q: int,
    plot_window: ForecastPlotWindow,
) -> None:
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

    std_disp = _std_residual_display(display, fit.label)
    diag: ResidualDiagnosticResults
    if fit.joint:
        plot_standardized_residuals(
            fit.garch.standardized_residuals,
            model_dir / f"{tag}_std_residuals.png",
            display,
            title_suffix=f"{fit.label} (gemeinsam geschaetzt)",
        )
        diag = run_residual_diagnostics(
            fit.garch.standardized_residuals,
            model_dir,
            tag,
            std_disp,
            model_label=f"{fit.label} (gemeinsam)",
            include_arch=True,
        )
    else:
        assert fit.arma_fitted is not None
        arma_resid_display = SeriesDisplay(
            short_name=f"Residuen nach ARMA({arma_p},{arma_q})",
            value_axis=f"Residuen (ARMA({arma_p},{arma_q}))",
            data_basis=display.data_basis,
        )
        plot_residuals(
            train_lr.loc[fit.arma_fitted.index],
            fit.arma_fitted,
            model_dir / f"{tag}_arma_residuals.png",
            arma_resid_display,
        )
        run_model_fit_diagnostics(
            train_lr,
            fit.arma_fitted,
            model_dir,
            f"{tag}_arma",
            display,
            arma_resid_display,
            model_label=f"ARMA({arma_p},{arma_q})",
        )
        plot_standardized_residuals(
            fit.garch.standardized_residuals,
            model_dir / f"{tag}_std_residuals.png",
            display,
            title_suffix=fit.label,
        )
        diag = run_residual_diagnostics(
            fit.garch.standardized_residuals,
            model_dir,
            tag,
            std_disp,
            model_label=fit.label,
            include_arch=True,
        )

    plot_conditional_volatility(
        fit.garch.conditional_volatility,
        model_dir / f"{tag}_conditional_vol.png",
        display,
        title_suffix=fit.label,
    )

    model_label = fit.label
    title_base = f"{model_label} – {ctx.study.analysis_label} [{ctx.mode_config.slug}]"

    def _fc_factory(steps: int, index) -> object:
        return forecast_arma_garch(
            fit, steps=steps, index=index, quantiles=DEFAULT_QUANTILES
        )

    fwd_factory = None
    if not ctx.holdout_lr.empty:
        fit_fwd = fit_arma_garch(
            ctx.forward_train_lr,
            ctx.mode_config,
            arma_order=(arma_p, arma_q),
            garch_p=garch_p,
            garch_q=garch_q,
        )

        def _fwd_factory(steps: int, index) -> object:
            return forecast_arma_garch(
                fit_fwd, steps=steps, index=index, quantiles=DEFAULT_QUANTILES
            )

        fwd_factory = _fwd_factory

    write_thesis_forecast_plots(
        train_lr=train_lr,
        holdout_lr=ctx.holdout_lr,
        horizons=ctx.horizons,
        forward_train_lr=ctx.forward_train_lr,
        forecast_factory=_fc_factory,
        forward_forecast_factory=fwd_factory,
        out_dir=model_dir,
        file_tag=tag,
        title_base=title_base,
        model_label=model_label,
        plot_window=plot_window,
        y_label=_forecast_ylabel(ctx),
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
    summary.extend(
        [
            "",
            format_residual_diagnostics(
                diag,
                model_label=fit.label,
                residual_label=std_disp.short_name,
            ),
        ]
    )
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
    add_forecast_plot_window_arguments(parser)
    args = parser.parse_args()

    mode_config = get_analysis_mode_config(args.analysis_mode)
    arma_p, arma_q = (int(x.strip()) for x in args.order.split(","))
    garch_p, garch_q = (int(x.strip()) for x in args.garch_order.split(","))
    models = {m.strip().lower() for m in args.models.split(",") if m.strip()}

    plot_window = forecast_plot_window_from_args(args)

    check_connection()
    with get_session() as session:
        ctx = load_tsa_context(
            session,
            mode_config,
            start_date=args.start_date,
            end_date=args.end_date,
            forecast_end=args.forecast_end,
            plot_window=plot_window,
        )

    out = resolve_output_dir() / f"tsa_{ctx.label}"
    out.mkdir(parents=True, exist_ok=True)

    print(f"Analysemodus: {mode_config.slug} – {mode_config.label_de}")
    print(f"TSA: {ctx.study.analysis_label}")
    print(f"Prognose-Grafikfenster: {plot_window.label_de}")
    print(f"Ausgabe: {out}")

    if "arma" in models:
        _run_arma(ctx, out, arma_p, arma_q, plot_window)
    if "garch" in models:
        _run_garch(ctx, out, garch_p, garch_q, plot_window)
    if "arma-garch" in models or "arma_garch" in models:
        _run_arma_garch(ctx, out, arma_p, arma_q, garch_p, garch_q, plot_window)

    print("TSA fertig.")


if __name__ == "__main__":
    main()
