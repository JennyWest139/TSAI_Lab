"""Tag-Zuordnungen fuer Zeitreihen, Korrelation und TSA (n:m)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tslab.db.models import EntityTagLink, Tag
from tslab.services.tag_service import get_tag, is_protected_tag
from tslab.services.timeseries_store import get_series_by_slug

ENTITY_SERIES = "series"
ENTITY_CORRELATION = "correlation"
ENTITY_TSA = "tsa"


def list_tag_ids(session: Session, entity_type: str, entity_id: int) -> list[int]:
    rows = session.scalars(
        select(EntityTagLink.tag_id)
        .where(
            EntityTagLink.entity_type == entity_type,
            EntityTagLink.entity_id == entity_id,
        )
        .order_by(EntityTagLink.tag_id)
    ).all()
    return list(rows)


def list_tag_names(session: Session, entity_type: str, entity_id: int) -> list[str]:
    rows = session.scalars(
        select(Tag.name)
        .join(EntityTagLink, EntityTagLink.tag_id == Tag.id)
        .where(
            EntityTagLink.entity_type == entity_type,
            EntityTagLink.entity_id == entity_id,
        )
        .order_by(Tag.name)
    ).all()
    return list(rows)


def entity_ids_with_tag(session: Session, entity_type: str, tag_id: int) -> list[int]:
    return list(
        session.scalars(
            select(EntityTagLink.entity_id).where(
                EntityTagLink.entity_type == entity_type,
                EntityTagLink.tag_id == tag_id,
            )
        ).all()
    )


def set_tags(
    session: Session, entity_type: str, entity_id: int, tag_ids: list[int]
) -> list[int]:
    """Ersetzt Tag-Zuordnungen; prueft Existenz der Tags."""
    clean: list[int] = []
    seen: set[int] = set()
    for raw in tag_ids:
        tid = int(raw)
        if tid in seen:
            continue
        if get_tag(session, tid) is None:
            raise ValueError("Tag nicht gefunden.")
        seen.add(tid)
        clean.append(tid)

    session.execute(
        delete(EntityTagLink).where(
            EntityTagLink.entity_type == entity_type,
            EntityTagLink.entity_id == entity_id,
        )
    )
    for tid in clean:
        session.add(
            EntityTagLink(entity_type=entity_type, entity_id=entity_id, tag_id=tid)
        )
    session.commit()
    return clean


def assign_series_tags(session: Session, series_id: int, tag_ids: list[int]) -> list[int]:
    return set_tags(session, ENTITY_SERIES, series_id, tag_ids)


def inherit_tags_from_series_slugs(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    series_slugs: list[str],
) -> list[int]:
    """Uebernimmt Vereinigung aller Tags der beteiligten Zeitreihen."""
    merged: list[int] = []
    seen: set[int] = set()
    for slug in series_slugs:
        ts = get_series_by_slug(session, slug)
        if ts is None:
            continue
        for tid in list_tag_ids(session, ENTITY_SERIES, ts.id):
            if tid not in seen:
                seen.add(tid)
                merged.append(tid)
    if merged:
        set_tags(session, entity_type, entity_id, merged)
    return merged


def has_protected_tag(session: Session, entity_type: str, entity_id: int) -> bool:
    for tid in list_tag_ids(session, entity_type, entity_id):
        if is_protected_tag(get_tag(session, tid)):
            return True
    return False


def entity_matches_tag_name(
    session: Session,
    entity_type: str,
    entity_id: int,
    tag_name: str,
    *,
    series_slugs: list[str] | None = None,
) -> bool:
    """Filter: Tag-Name auf Entitaet oder verknuepfte Zeitreihen."""
    needle = tag_name.strip().lower()
    if not needle:
        return True
    for name in list_tag_names(session, entity_type, entity_id):
        if name.strip().lower() == needle:
            return True
    if not series_slugs:
        return False
    for slug in series_slugs:
        ts = get_series_by_slug(session, slug)
        if ts is None:
            continue
        for name in list_tag_names(session, ENTITY_SERIES, ts.id):
            if name.strip().lower() == needle:
                return True
    return False
