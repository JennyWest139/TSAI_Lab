#!/usr/bin/env python
"""
Koeffizienten-Abgleich Python vs. Diplomarbeit (R/rugarch).

Beispiel (PDF-Abgleich Training bis 07/2006):
  python scripts/compare_thesis_coefficients.py --from-db
  python scripts/compare_thesis_coefficients.py --from-db --end-date 2006-07-01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.config_loader import resolve_output_dir
from tslab.db.engine import check_connection, get_session
from tslab.services.analysis_mode import (
    AnalysisMode,
    add_analysis_mode_argument,
    get_analysis_mode_config,
    resolve_study_dates_for_mode,
)
from tslab.services.models_arma import fit_arma
from tslab.services.models_garch import fit_arma_garch, fit_garch
from tslab.services.tsa_context import load_tsa_context
from tslab.services.thesis_coefficients import (
    compare_parameters,
    comparisons_to_dataframe,
    extract_arma_garch_joint_r_style,
    extract_arma_params_r_style,
    extract_garch_params_r_style,
    format_coefficient_abgleich,
    load_thesis_reference,
)


def _run_abgleich(
    *,
    mode_config,
    start_date: str | None,
    end_date: str | None,
    reference_path: Path | None,
) -> tuple[str, Path]:
    ref = load_thesis_reference(reference_path)
    study_cfg = ref.get("study", {})
    eff_start = start_date or study_cfg.get("start_date")
    eff_end = end_date or study_cfg.get("end_date")

    with get_session() as session:
        ctx = load_tsa_context(
            session,
            mode_config=mode_config,
            start_date=eff_start,
            end_date=eff_end,
        )
        y = ctx.train_lr
        arma_res, _ = fit_arma(y, (1, 1))
        garch_fit = fit_garch(y, mode_config, p=1, q=1)
        ag_fit = fit_arma_garch(y, mode_config, arma_order=(1, 1), garch_p=1, garch_q=1)

    models = ref.get("models", {})
    rows = []
    rows.extend(
        compare_parameters(
            "arma11",
            models["arma11"],
            extract_arma_params_r_style(arma_res),
        )
    )
    rows.extend(
        compare_parameters(
            "garch11",
            models["garch11"],
            extract_garch_params_r_style(garch_fit),
        )
    )
    rows.extend(
        compare_parameters(
            "arma11_garch11_joint",
            models["arma11_garch11_joint"],
            extract_arma_garch_joint_r_style(ag_fit),
        )
    )

    study_label = f"{eff_start} bis {eff_end} ({mode_config.slug})"
    report = format_coefficient_abgleich(
        rows, study_label=study_label, n_obs=len(y)
    )

    label = f"{ctx.study.start_date.date()}_to_{ctx.study.cutoff.date()}"
    out = resolve_output_dir() / f"coefficient_abgleich_{mode_config.slug}_{label}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "coefficient_abgleich.txt").write_text(report, encoding="utf-8")
    comparisons_to_dataframe(rows).to_csv(
        out / "coefficient_abgleich.csv", index=False, encoding="utf-8-sig"
    )
    return report, out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Koeffizienten-Abgleich mit Diplomarbeit JW 2008"
    )
    add_analysis_mode_argument(parser, required=False)
    parser.set_defaults(analysis_mode=AnalysisMode.THESIS)
    parser.add_argument("--start-date", default=None, help="Analyse-Start (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="Cutoff / Analyse-Ende")
    parser.add_argument("--from-db", action="store_true", help="PDAX aus DB (slug pdax)")
    parser.add_argument(
        "--reference",
        default=None,
        help="Pfad zu thesis_reference_coefficients.yaml",
    )
    args = parser.parse_args()

    mode_config = get_analysis_mode_config(args.analysis_mode)
    eff_start, eff_end = resolve_study_dates_for_mode(
        mode_config, start_date=args.start_date, end_date=args.end_date
    )
    if args.end_date is None:
        ref = load_thesis_reference(
            Path(args.reference) if args.reference else None
        )
        eff_end = ref.get("study", {}).get("end_date", eff_end)

    if args.from_db:
        check_connection()

    report, out = _run_abgleich(
        mode_config=mode_config,
        start_date=eff_start,
        end_date=eff_end,
        reference_path=Path(args.reference) if args.reference else None,
    )
    print(report)
    print(f"Gespeichert: {out}")


if __name__ == "__main__":
    main()
