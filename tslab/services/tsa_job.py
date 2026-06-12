"""TSA ausfuehren und Artefakte schreiben (ARMA / GARCH / ARMA-GARCH)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from tslab.config_loader import resolve_output_dir
from tslab.plots.series_display import SeriesDisplay
from tslab.plots.time_series_plots import plot_residuals, plot_series
from tslab.plots.tsa_plots import plot_conditional_volatility, plot_standardized_residuals
from tslab.services.analysis_mode import AnalysisMode, AnalysisModeConfig, returns_display
from tslab.services.forecast_plot_service import (
    arma_volatility_forecast,
    write_thesis_forecast_plots,
)
from tslab.services.forecast_plot_window import ForecastPlotWindow, resolve_forecast_plot_window
from tslab.services.models_arma import fit_arma
from tslab.services.models_garch import (
    DEFAULT_QUANTILES,
    forecast_arma_garch,
    forecast_garch,
    fit_arma_garch,
    fit_garch,
)
from tslab.services.residual_diagnostics import (
    ResidualDiagnosticResults,
    format_residual_diagnostics,
    run_model_fit_diagnostics,
    run_residual_diagnostics,
)
from tslab.services.thesis_coefficients import (
    compare_parameters,
    extract_arma_garch_joint_r_style,
    extract_arma_params_r_style,
    extract_garch_params_r_style,
    format_coefficient_abgleich,
    load_thesis_reference,
)
from tslab.services.tsa_context import TSAContext, load_tsa_context


@dataclass(frozen=True)
class TsaJobResult:
    output_dir: Path
    context: TSAContext
    models_run: list[str]
    series_slug: str


def _level_context_kwargs(ctx: TSAContext, plot_window: ForecastPlotWindow) -> dict:
    return {
        "mode_config": ctx.mode_config,
        "train_prices": ctx.train_prices,
        "holdout_prices": ctx.holdout_prices,
        "forward_train_prices": ctx.forward_train_prices,
        "price_at_cutoff": ctx.price_at_cutoff,
        "price_at_last_actual": ctx.price_at_last_actual,
        "plot_window": plot_window,
    }


def _forecast_ylabel(ctx: TSAContext) -> str:
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
    ctx: TSAContext, out: Path, p: int, q: int, plot_window: ForecastPlotWindow
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

    level_summaries = write_thesis_forecast_plots(
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
        y_label=_forecast_ylabel(ctx),
        **_level_context_kwargs(ctx, plot_window),
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
    for block in level_summaries:
        summary.extend(["", block])
    (model_dir / "summary.txt").write_text("\n".join(summary), encoding="utf-8")


def _run_garch(
    ctx: TSAContext, out: Path, p: int, q: int, plot_window: ForecastPlotWindow
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
        fit_fwd = fit_garch(ctx.forward_train_lr, ctx.mode_config, p=p, q=q)

        def _fwd_factory(steps: int, index) -> object:
            return forecast_garch(
                fit_fwd, steps=steps, index=index, quantiles=DEFAULT_QUANTILES
            )

        fwd_factory = _fwd_factory

    level_summaries = write_thesis_forecast_plots(
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
        y_label=_forecast_ylabel(ctx),
        **_level_context_kwargs(ctx, plot_window),
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
    for block in level_summaries:
        summary.extend(["", block])
    (model_dir / "summary.txt").write_text("\n".join(summary), encoding="utf-8")


def _run_arma_garch(
    ctx: TSAContext,
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

    level_summaries = write_thesis_forecast_plots(
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
        y_label=_forecast_ylabel(ctx),
        **_level_context_kwargs(ctx, plot_window),
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
    for block in level_summaries:
        summary.extend(["", block])
    (model_dir / "summary.txt").write_text("\n".join(summary), encoding="utf-8")


def _write_coefficient_abgleich(
    ctx: TSAContext,
    out: Path,
    *,
    models: set[str],
    arma_p: int,
    arma_q: int,
    garch_p: int,
    garch_q: int,
) -> str | None:
    if ctx.mode_config.mode is not AnalysisMode.THESIS:
        return None

    ref = load_thesis_reference()
    ref_models = ref.get("models", {})
    y = ctx.train_lr
    abgleich_rows = []
    if "arma11" in ref_models and "arma" in models:
        arma_res, _ = fit_arma(y, (arma_p, arma_q))
        abgleich_rows.extend(
            compare_parameters(
                "arma11",
                ref_models["arma11"],
                extract_arma_params_r_style(arma_res),
            )
        )
    if "garch11" in ref_models and "garch" in models:
        g_fit = fit_garch(y, ctx.mode_config, p=garch_p, q=garch_q)
        abgleich_rows.extend(
            compare_parameters(
                "garch11",
                ref_models["garch11"],
                extract_garch_params_r_style(g_fit),
            )
        )
    if "arma11_garch11_joint" in ref_models and (
        "arma-garch" in models or "arma_garch" in models
    ):
        ag_fit = fit_arma_garch(
            y,
            ctx.mode_config,
            arma_order=(arma_p, arma_q),
            garch_p=garch_p,
            garch_q=garch_q,
        )
        abgleich_rows.extend(
            compare_parameters(
                "arma11_garch11_joint",
                ref_models["arma11_garch11_joint"],
                extract_arma_garch_joint_r_style(ag_fit),
            )
        )
    if not abgleich_rows:
        return None

    abgleich_text = format_coefficient_abgleich(
        abgleich_rows,
        study_label=f"{ctx.study.analysis_label} [{ctx.mode_config.slug}]",
        n_obs=len(y),
    )
    (out / "coefficient_abgleich.txt").write_text(abgleich_text, encoding="utf-8")
    return abgleich_text


def _normalize_models(models: set[str] | list[str] | None) -> set[str]:
    if not models:
        return {"arma", "garch", "arma-garch"}
    return {str(m).strip().lower() for m in models if str(m).strip()}


def run_tsa_job(
    session: Session,
    mode_config: AnalysisModeConfig,
    *,
    series_slug: str = "pdax",
    start_date: str | None = None,
    end_date: str | None = None,
    forecast_end: str | None = None,
    models: set[str] | list[str] | None = None,
    arma_order: tuple[int, int] = (1, 1),
    garch_order: tuple[int, int] = (1, 1),
    plot_window: ForecastPlotWindow | None = None,
    output_root: Path | None = None,
    run_coefficient_abgleich: bool = True,
) -> TsaJobResult:
    """Fuehrt TSA aus und schreibt Output-Artefakte."""
    model_set = _normalize_models(models)
    arma_p, arma_q = arma_order
    garch_p, garch_q = garch_order
    eff_window = plot_window or ForecastPlotWindow.from_defaults()

    ctx = load_tsa_context(
        session,
        mode_config,
        series_slug=series_slug,
        start_date=start_date,
        end_date=end_date,
        forecast_end=forecast_end,
        plot_window=eff_window,
    )

    out = (output_root or resolve_output_dir()) / f"tsa_{ctx.label}"
    out.mkdir(parents=True, exist_ok=True)

    models_run: list[str] = []
    if "arma" in model_set:
        _run_arma(ctx, out, arma_p, arma_q, eff_window)
        models_run.append("arma")
    if "garch" in model_set:
        _run_garch(ctx, out, garch_p, garch_q, eff_window)
        models_run.append("garch")
    if "arma-garch" in model_set or "arma_garch" in model_set:
        _run_arma_garch(ctx, out, arma_p, arma_q, garch_p, garch_q, eff_window)
        models_run.append("arma-garch")

    if run_coefficient_abgleich:
        _write_coefficient_abgleich(
            ctx,
            out,
            models=model_set,
            arma_p=arma_p,
            arma_q=arma_q,
            garch_p=garch_p,
            garch_q=garch_q,
        )

    return TsaJobResult(
        output_dir=out,
        context=ctx,
        models_run=models_run,
        series_slug=series_slug,
    )


def forecast_plot_window_from_payload(payload: dict) -> ForecastPlotWindow:
    """Plot-Fenster aus Web-Formular oder CLI-aehnlichen Werten."""
    def _float(key: str) -> float | None:
        raw = payload.get(key)
        if raw is None or raw == "":
            return None
        return float(raw)

    return resolve_forecast_plot_window(
        pre_years=_float("plot_pre_years"),
        forecast_years=_float("plot_forecast_years"),
        post_years=_float("plot_post_years"),
    )
