"""Koeffizienten-Extraktion und Abgleich mit Diplomarbeit (R/rugarch)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from tslab.config_loader import project_root
from tslab.services.models_garch import (
    ArmaGarchFitResult,
    GarchFitResult,
    GARCH_SCALE,
)

DEFAULT_REFERENCE_PATH = project_root() / "config" / "thesis_reference_coefficients.yaml"


@dataclass(frozen=True)
class CoefficientComparison:
    model_id: str
    label: str
    parameter: str
    reference: float | None
    estimated: float | None
    delta: float | None
    within_tolerance: bool | None
    note: str = ""

    @property
    def status(self) -> str:
        if self.note:
            return "skip"
        if self.within_tolerance is None:
            return "n/a"
        return "ok" if self.within_tolerance else "diff"


def load_thesis_reference(
    path: Path | None = None,
) -> dict[str, Any]:
    ref_path = path or DEFAULT_REFERENCE_PATH
    with ref_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def extract_arma_params_r_style(arma_result: object) -> dict[str, float]:
    """statsmodels ARMA -> Vorzeichen wie R-Arima-Ausgabe in der Diplomarbeit."""
    params = arma_result.params
    out = {
        "intercept": float(params["const"]),
        "ar1": -float(params["ar.L1"]),
        "ma1": -float(params["ma.L1"]),
        "sigma2": float(params["sigma2"]),
        "aic": float(arma_result.aic),
        "n_obs": float(arma_result.nobs),
    }
    return out


def extract_garch_params_r_style(fit: GarchFitResult) -> dict[str, float]:
    """arch GARCH -> omega auf unskalierten Renditen, mu in Originaleinheiten."""
    params = fit.result.params
    scale = fit.scale
    mu = 0.0
    if "mu" in params.index:
        mu = float(params["mu"]) / scale
    elif "Const" in params.index:
        mu = float(params["Const"]) / scale
    return {
        "mu": mu,
        "omega": float(params["omega"]) / (scale**2),
        "alpha1": float(params["alpha[1]"]),
        "beta1": float(params["beta[1]"]),
        "aic": fit.aic,
        "n_obs": float(fit.result.nobs),
    }


def extract_arma_garch_joint_r_style(fit: ArmaGarchFitResult) -> dict[str, float]:
    """Gemeinsames arch-Modell; MA-Term fehlt (nur AR(1)+GARCH)."""
    params = fit.garch.result.params
    scale = fit.garch.scale
    mu = fit.mean_offset
    ar1 = 0.0
    if "Const" in params.index:
        mu += float(params["Const"]) / scale
    for key in params.index:
        kl = key.lower()
        if key in ("Const", "mu") or "omega" in kl or "alpha" in kl or "beta" in kl:
            continue
        ar1 = -float(params[key])
        break
    return {
        "mu": mu,
        "ar1": ar1,
        "ma1": float("nan"),
        "omega": float(params["omega"]) / (scale**2),
        "alpha1": float(params["alpha[1]"]),
        "beta1": float(params["beta[1]"]),
        "aic": fit.garch.aic,
        "n_obs": float(fit.garch.result.nobs),
        "joint": float(fit.joint),
        "garch_scale": scale,
    }


def _within_tolerance(
    reference: float,
    estimated: float,
    *,
    abs_tol: float,
    rel_tol: float,
) -> bool:
    delta = abs(estimated - reference)
    if delta <= abs_tol:
        return True
    denom = max(abs(reference), 1e-12)
    return (delta / denom) <= rel_tol


def compare_parameters(
    model_id: str,
    model_cfg: dict[str, Any],
    estimated: dict[str, float],
) -> list[CoefficientComparison]:
    label = str(model_cfg.get("label", model_id))
    ref_params: dict[str, float] = model_cfg.get("parameters", {})
    tol = model_cfg.get("tolerances", {})
    abs_tol = float(tol.get("abs", 0.05))
    rel_tol = float(tol.get("rel", 0.15))
    skip = set(model_cfg.get("skip_parameters", []))

    rows: list[CoefficientComparison] = []
    for name, reference in ref_params.items():
        if name in skip:
            rows.append(
                CoefficientComparison(
                    model_id=model_id,
                    label=label,
                    parameter=name,
                    reference=float(reference),
                    estimated=estimated.get(name),
                    delta=None,
                    within_tolerance=None,
                    note=model_cfg.get("python_spec", "In Python nicht geschaetzt (Spec-Abweichung)"),
                )
            )
            continue
        est = estimated.get(name)
        if est is None or (isinstance(est, float) and pd.isna(est)):
            rows.append(
                CoefficientComparison(
                    model_id=model_id,
                    label=label,
                    parameter=name,
                    reference=float(reference),
                    estimated=None,
                    delta=None,
                    within_tolerance=None,
                    note="Nicht geschaetzt",
                )
            )
            continue
        est_f = float(est)
        ref_f = float(reference)
        delta = est_f - ref_f
        rows.append(
            CoefficientComparison(
                model_id=model_id,
                label=label,
                parameter=name,
                reference=ref_f,
                estimated=est_f,
                delta=delta,
                within_tolerance=_within_tolerance(
                    ref_f, est_f, abs_tol=abs_tol, rel_tol=rel_tol
                ),
            )
        )

    if model_cfg.get("compare_information_criteria", True):
        ic = model_cfg.get("information_criteria", {})
        if "aic" in ic and "aic" in estimated:
            ref_aic = float(ic["aic"])
            est_aic = float(estimated["aic"])
            rows.append(
                CoefficientComparison(
                    model_id=model_id,
                    label=label,
                    parameter="aic",
                    reference=ref_aic,
                    estimated=est_aic,
                    delta=est_aic - ref_aic,
                    within_tolerance=_within_tolerance(
                        ref_aic, est_aic, abs_tol=abs_tol, rel_tol=rel_tol
                    ),
                )
            )
    return rows


def format_coefficient_abgleich(
    rows: list[CoefficientComparison],
    *,
    study_label: str,
    n_obs: int | None = None,
) -> str:
    lines = [
        "Koeffizienten-Abgleich Diplomarbeit (R) vs. Python",
        f"Stichprobe: {study_label}",
    ]
    if n_obs is not None:
        lines.append(f"n (Training Renditen): {n_obs}")
    lines.append("")

    current_model = ""
    for row in rows:
        if row.model_id != current_model:
            current_model = row.model_id
            lines.append(f"--- {row.label} [{row.model_id}] ---")
        if row.note:
            lines.append(
                f"  {row.parameter:10s}  ref={row.reference!s:>14}  "
                f"(uebersprungen: {row.note})"
            )
            continue
        if row.estimated is None:
            lines.append(f"  {row.parameter:10s}  ref={row.reference!s:>14}  (fehlt)")
            continue
        flag = "OK" if row.within_tolerance else "ABWEICHUNG"
        lines.append(
            f"  {row.parameter:10s}  ref={row.reference:>14.6g}  "
            f"py={row.estimated:>14.6g}  delta={row.delta:>+12.4g}  [{flag}]"
        )
    lines.append("")
    lines.append(
        "Hinweis: ARMA via statsmodels (innovations_mle), Vorzeichen auf R-Nomenklatur "
        "gemappt (ar1=-ar.L1, ma1=-ma.L1). GARCH-omega ohne GARCH_SCALE. "
        "Gemeinsames ARMA-GARCH in R enthaelt MA-Term; arch nur AR(1)+GARCH."
    )
    return "\n".join(lines)


def comparisons_to_dataframe(rows: list[CoefficientComparison]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "model_id": r.model_id,
                "label": r.label,
                "parameter": r.parameter,
                "reference": r.reference,
                "estimated": r.estimated,
                "delta": r.delta,
                "status": r.status,
                "note": r.note,
            }
            for r in rows
        ]
    )
