"""Tag-Stammdaten (Reporting u. a.)."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from tslab.db.models import EntityTagLink, Tag

PROTECTED_TAG = "Reporting"


def list_tags(session: Session) -> list[Tag]:
    return list(session.scalars(select(Tag).order_by(Tag.name)).all())


def get_tag(session: Session, tag_id: int) -> Tag | None:
    return session.get(Tag, tag_id)


def get_tag_by_name(session: Session, name: str) -> Tag | None:
    return session.scalar(select(Tag).where(func.lower(Tag.name) == name.strip().lower()))


def seed_default_tags(session: Session) -> Tag | None:
    """Legt geschuetzten Standard-Tag an."""
    existing = get_tag_by_name(session, PROTECTED_TAG)
    if existing:
        return existing
    row = Tag(name=PROTECTED_TAG)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def is_protected_tag(tag: Tag | None) -> bool:
    return tag is not None and tag.name.strip().lower() == PROTECTED_TAG.lower()


def series_has_protected_tag(session: Session, series_id: int) -> bool:
    from tslab.services.entity_tags import ENTITY_SERIES, list_tag_ids

    for tid in list_tag_ids(session, ENTITY_SERIES, series_id):
        if is_protected_tag(get_tag(session, tid)):
            return True
    return False


def create_tag(session: Session, name: str) -> Tag:
    clean = name.strip()
    if not clean:
        raise ValueError("Tag-Name darf nicht leer sein.")
    if clean.lower() == PROTECTED_TAG.lower():
        raise ValueError(f"Tag '{PROTECTED_TAG}' ist reserviert.")
    if get_tag_by_name(session, clean):
        raise ValueError(f"Tag '{clean}' existiert bereits.")
    row = Tag(name=clean)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_tag(session: Session, tag_id: int, name: str) -> Tag:
    row = get_tag(session, tag_id)
    if row is None:
        raise ValueError("Tag nicht gefunden.")
    if is_protected_tag(row):
        raise ValueError(f"Tag '{PROTECTED_TAG}' darf nicht umbenannt werden.")
    clean = name.strip()
    if not clean:
        raise ValueError("Tag-Name darf nicht leer sein.")
    other = get_tag_by_name(session, clean)
    if other is not None and other.id != tag_id:
        raise ValueError(f"Tag '{clean}' existiert bereits.")
    row.name = clean
    session.commit()
    session.refresh(row)
    return row


def delete_tag(session: Session, tag_id: int) -> None:
    row = get_tag(session, tag_id)
    if row is None:
        raise ValueError("Tag nicht gefunden.")
    if is_protected_tag(row):
        raise ValueError(f"Tag '{PROTECTED_TAG}' darf nicht geloescht werden.")
    session.execute(delete(EntityTagLink).where(EntityTagLink.tag_id == tag_id))
    session.delete(row)
    session.commit()
