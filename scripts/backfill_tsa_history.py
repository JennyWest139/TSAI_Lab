"""Bestehende output/tsa_*-Ordner in tsa_history importieren."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from tslab.config_loader import resolve_output_dir
from tslab.db.engine import get_session, init_db
from tslab.db.models import TsaHistory

_FOLDER_RE = re.compile(
    r"^tsa_(?P<mode>thesis|extended)_(?P<start>\d{4}-\d{2}-\d{2})_to_(?P<end>\d{4}-\d{2}-\d{2})$"
)


def _parse_folder(name: str) -> dict | None:
    m = _FOLDER_RE.match(name)
    if not m:
        return None
    return {
        "analysis_mode": m.group("mode"),
        "train_start": m.group("start"),
        "train_end": m.group("end"),
    }


def backfill_tsa_history(*, dry_run: bool = False) -> int:
    init_db()
    root = resolve_output_dir()
    added = 0
    with get_session() as session:
        existing_dirs = {
            r.output_dir
            for r in session.scalars(select(TsaHistory.output_dir)).all()
            if r.output_dir
        }
        for path in sorted(root.glob("tsa_*")):
            if not path.is_dir():
                continue
            out_str = str(path.resolve())
            if out_str in existing_dirs:
                continue
            meta = _parse_folder(path.name) or {}
            models = ["arma-garch"]
            summary = path / "summary.txt"
            if summary.is_file():
                text = summary.read_text(encoding="utf-8", errors="replace")
                if "arma-garch" in text.lower() or "arma_garch" in text.lower():
                    models = ["arma-garch"]
                elif "garch" in text.lower():
                    models = ["garch"]
                elif "arma" in text.lower():
                    models = ["arma"]
            row = TsaHistory(
                series_slug="pdax",
                analysis_mode=meta.get("analysis_mode", "thesis"),
                models=json.dumps(models),
                train_start=meta.get("train_start"),
                train_end=meta.get("train_end"),
                forecast_end=None,
                status="fertig",
                output_dir=out_str,
                created_at=datetime.fromtimestamp(path.stat().st_mtime),
            )
            if dry_run:
                print(f"Would add: {path.name}")
            else:
                session.add(row)
            added += 1
        if not dry_run:
            session.commit()
    return added


if __name__ == "__main__":
    n = backfill_tsa_history()
    print(f"Backfilled {n} TSA history row(s).")
