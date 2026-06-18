#!/usr/bin/env python
"""
KI-Bericht (Word) fuer einen bestehenden Output-Lauf erstellen.

Beispiele:
  python scripts/generate_run_report.py output/correlation/pdax_dax_20250618
  python scripts/generate_run_report.py output/tsa/pdax_arima --model openai:gpt-4o-mini
  TSLAB_AI_REPORTS_ENABLED=1 python scripts/generate_run_report.py output/correlation/...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.config_loader import load_dotenv_file
from tslab.services.report_service import generate_run_report, list_report_models, load_report_config


def main() -> int:
    load_dotenv_file()
    parser = argparse.ArgumentParser(description="KI-Bericht (.docx) fuer Output-Ordner")
    parser.add_argument("output_dir", help="Pfad zum Lauf-Ordner (relativ oder absolut)")
    parser.add_argument(
        "--model",
        default=None,
        help=f"Modell-ID (Standard: {load_report_config().default_model})",
    )
    parser.add_argument(
        "--run-type",
        default="Analyse",
        help="Titel-Zusatz: Korrelation, TSA, …",
    )
    parser.add_argument("--list-models", action="store_true", help="Verfuegbare Modelle anzeigen")
    args = parser.parse_args()

    if args.list_models:
        for m in list_report_models(include_disabled=True):
            avail = "ok" if m.get("available") else "—"
            print(f"{m['id']}\t{m['label']}\t[{avail}]")
        return 0

    result = generate_run_report(
        args.output_dir,
        model_id=args.model,
        run_type=args.run_type,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
