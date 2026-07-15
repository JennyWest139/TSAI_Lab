#!/usr/bin/env python
"""Korrelations- und TSA-Historie leeren (z. B. nach Workspace-Umzug).

Zeitreihen und Beobachtungen bleiben unberuehrt. Nur Historie-Eintraege,
deren Kategorie-Zuordnungen und TSA-Prognosewerte werden entfernt.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, func, select

from tslab.db.engine import get_session, init_db
from tslab.db.models import CorrelationHistory, EntityCategory, EntityTag, TsaForecastValue, TsaHistory
from tslab.services.entity_categories import ENTITY_CORRELATION, ENTITY_TSA


def _counts(session) -> dict[str, int]:
    return {
        "correlation_history": session.scalar(select(func.count()).select_from(CorrelationHistory)) or 0,
        "tsa_history": session.scalar(select(func.count()).select_from(TsaHistory)) or 0,
        "tsa_forecast_values": session.scalar(select(func.count()).select_from(TsaForecastValue)) or 0,
        "entity_categories_corr": session.scalar(
            select(func.count()).select_from(EntityCategory).where(EntityCategory.entity_type == ENTITY_CORRELATION)
        )
        or 0,
        "entity_categories_tsa": session.scalar(
            select(func.count()).select_from(EntityCategory).where(EntityCategory.entity_type == ENTITY_TSA)
        )
        or 0,
        "entity_tags_corr": session.scalar(
            select(func.count()).select_from(EntityTag).where(EntityTag.entity_type == ENTITY_CORRELATION)
        )
        or 0,
        "entity_tags_tsa": session.scalar(
            select(func.count()).select_from(EntityTag).where(EntityTag.entity_type == ENTITY_TSA)
        )
        or 0,
    }


def clear_run_history(*, dry_run: bool = False) -> dict[str, int]:
    init_db()
    with get_session() as session:
        before = _counts(session)
        if dry_run:
            return before

        session.execute(delete(EntityCategory).where(EntityCategory.entity_type == ENTITY_CORRELATION))
        session.execute(delete(EntityCategory).where(EntityCategory.entity_type == ENTITY_TSA))
        session.execute(delete(EntityTag).where(EntityTag.entity_type == ENTITY_CORRELATION))
        session.execute(delete(EntityTag).where(EntityTag.entity_type == ENTITY_TSA))
        session.execute(delete(TsaForecastValue))
        session.execute(delete(CorrelationHistory))
        session.execute(delete(TsaHistory))
        session.commit()
        return before


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur zaehlen, nichts loeschen",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Ohne Rueckfrage loeschen",
    )
    args = parser.parse_args()

    if args.dry_run:
        counts = clear_run_history(dry_run=True)
        print("Aktuelle Eintraege (dry-run):")
        for key, value in counts.items():
            print(f"  {key}: {value}")
        return

    if not args.yes:
        counts = clear_run_history(dry_run=True)
        total = counts["correlation_history"] + counts["tsa_history"]
        print(f"Es werden {total} Historie-Laeufe geloescht (CORR: {counts['correlation_history']}, TSA: {counts['tsa_history']}).")
        print("Zeitreihen in der DB bleiben erhalten.")
        answer = input("Fortfahren? [j/N] ").strip().lower()
        if answer not in ("j", "ja", "y", "yes"):
            print("Abgebrochen.")
            return

    before = clear_run_history(dry_run=False)
    print("Historie geleert:")
    print(f"  Korrelation: {before['correlation_history']} Eintraege")
    print(f"  TSA: {before['tsa_history']} Eintraege")
    print(f"  TSA-Prognosewerte: {before['tsa_forecast_values']}")
    print("Zeitreihen unveraendert. Neue Laeufe schreiben nach output/ im aktuellen Projekt.")


if __name__ == "__main__":
    main()
