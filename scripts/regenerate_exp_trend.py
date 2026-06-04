#!/usr/bin/env python
"""Nur pdax_levels_exp_trend.png neu erzeugen."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.config_loader import load_defaults, resolve_output_dir
from tslab.plots import time_series_plots as plots
from tslab.plots.series_display import PDAX_ORIGINAL
from tslab.services.cutoff import split_at_cutoff
from tslab.services.ingest_werte import load_pdax_series

if __name__ == "__main__":
    cfg = load_defaults()
    cutoff = cfg.get("default_cutoff", "2007-06-30")
    train, _ = split_at_cutoff(load_pdax_series(), cutoff)
    out = resolve_output_dir(cfg) / f"phase0_cutoff_{cutoff}" / "pdax_levels"
    path = plots.plot_fitted_exponential(
        train, out / "pdax_levels_exp_trend.png", PDAX_ORIGINAL
    )
    print(f"OK: {path} ({path.stat().st_size} bytes)")
