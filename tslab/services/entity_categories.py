"""Kategorie-Zuordnungen fuer Zeitreihen, Korrelation und TSA (n:m)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tslab.db.models import Category, EntityCategory, TimeSeries
from tslab.services.category_service import get_category
from tslab.services.timeseries_store import get_series_by_slug

ENTITY_SERIES = "series"
ENTITY_CORRELATION = "correlation"
ENTITY_TSA = "tsa"


def list_category_ids(session: Session, entity_type: str, entity_id: int) -> list[int]:
    rows = session.scalars(
        select(EntityCategory.category_id)
        .where(
            EntityCategory.entity_type == entity_type,
            EntityCategory.entity_id == entity_id,
        )
        .order_by(EntityCategory.category_id)
    ).all()
    return list(rows)


def list_category_names(session: Session, entity_type: str, entity_id: int) -> list[str]:
    rows = session.scalars(
        select(Category.name)
        .join(EntityCategory, EntityCategory.category_id == Category.id)
        .where(
            EntityCategory.entity_type == entity_type,
            EntityCategory.entity_id == entity_id,
        )
        .order_by(Category.name)
    ).all()
    return list(rows)


def entity_ids_with_category(session: Session, entity_type: str, category_id: int) -> list[int]:
    return list(
        session.scalars(
            select(EntityCategory.entity_id).where(
                EntityCategory.entity_type == entity_type,
                EntityCategory.category_id == category_id,
            )
        ).all()
    )


def set_categories(
    session: Session, entity_type: str, entity_id: int, category_ids: list[int]
) -> list[int]:
    """Ersetzt Kategorie-Zuordnungen; prueft Existenz der Kategorien."""
    clean: list[int] = []
    seen: set[int] = set()
    for raw in category_ids:
        cid = int(raw)
        if cid in seen:
            continue
        if get_category(session, cid) is None:
            raise ValueError("Kategorie nicht gefunden.")
        seen.add(cid)
        clean.append(cid)

    session.execute(
        delete(EntityCategory).where(
            EntityCategory.entity_type == entity_type,
            EntityCategory.entity_id == entity_id,
        )
    )
    for cid in clean:
        session.add(
            EntityCategory(entity_type=entity_type, entity_id=entity_id, category_id=cid)
        )
    session.commit()
    return clean


def sync_series_primary_category(session: Session, series_id: int, category_ids: list[int]) -> None:
    """Haelt time_series.category_id als erste Zuordnung (Abwaertskompatibilitaet)."""
    ts = session.get(TimeSeries, series_id)
    if ts is None:
        return
    ts.category_id = category_ids[0] if category_ids else None
    session.commit()


def assign_series_categories(session: Session, series_id: int, category_ids: list[int]) -> list[int]:
    ids = set_categories(session, ENTITY_SERIES, series_id, category_ids)
    sync_series_primary_category(session, series_id, ids)
    return ids


def inherit_categories_from_series_slugs(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    series_slugs: list[str],
) -> list[int]:
    """Uebernimmt Vereinigung aller Kategorien der beteiligten Zeitreihen."""
    merged: list[int] = []
    seen: set[int] = set()
    for slug in series_slugs:
        ts = get_series_by_slug(session, slug)
        if ts is None:
            continue
        for cid in list_category_ids(session, ENTITY_SERIES, ts.id):
            if cid not in seen:
                seen.add(cid)
                merged.append(cid)
        if ts.category_id is not None and ts.category_id not in seen:
            seen.add(ts.category_id)
            merged.append(ts.category_id)
    if merged:
        set_categories(session, entity_type, entity_id, merged)
    return merged


def backfill_series_from_primary(session: Session) -> int:
    """Migration: category_id -> entity_categories."""
    count = 0
    rows = session.scalars(
        select(TimeSeries).where(TimeSeries.category_id.is_not(None))
    ).all()
    for ts in rows:
        existing = set(list_category_ids(session, ENTITY_SERIES, ts.id))
        if ts.category_id not in existing:
            session.add(
                EntityCategory(
                    entity_type=ENTITY_SERIES,
                    entity_id=ts.id,
                    category_id=ts.category_id,
                )
            )
            count += 1
    if count:
        session.commit()
    return count
