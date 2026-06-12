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

from tslab.db.engine import check_connection, get_session
from tslab.services.analysis_mode import add_analysis_mode_argument, get_analysis_mode_config
from tslab.services.forecast_plot_window import (
    add_forecast_plot_window_arguments,
    forecast_plot_window_from_args,
)
from tslab.services.tsa_job import run_tsa_job


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
        job = run_tsa_job(
            session,
            mode_config,
            start_date=args.start_date,
            end_date=args.end_date,
            forecast_end=args.forecast_end,
            models=models,
            arma_order=(arma_p, arma_q),
            garch_order=(garch_p, garch_q),
            plot_window=plot_window,
        )

    ctx = job.context
    print(f"Analysemodus: {mode_config.slug} – {mode_config.label_de}")
    print(f"TSA: {ctx.study.analysis_label}")
    print(f"Prognose-Grafikfenster: {plot_window.label_de}")
    print(f"Ausgabe: {job.output_dir}")
    for m in job.models_run:
        print(f"  Modell {m} fertig")
    print("TSA fertig.")


if __name__ == "__main__":
    main()
