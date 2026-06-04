#!/usr/bin/env python
"""Kurzinfo zu Werte.csv / PDAX (ohne Plots)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.services.ingest_werte import load_pdax_series

if __name__ == "__main__":
    s = load_pdax_series()
    print(f"PDAX: {len(s)} Beobachtungen")
    print(f"  von {s.index.min().date()} bis {s.index.max().date()}")
    print(f"  min={s.min():.2f}  max={s.max():.2f}  mean={s.mean():.2f}")
