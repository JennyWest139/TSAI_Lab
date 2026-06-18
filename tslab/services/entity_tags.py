"""Tags fuer Zeitreihen, Korrelation und TSA."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tslab.db.models import EntityTag

PROTECTED_TAG = "Reporting"
ENTITY_SERIES = "series"
ENTITY_CORRELATION = "correlation"
ENTITY_TSA = "tsa"


def list_tags(session: Session, entity_type: str, entity_id: int) -> list[str]:
    rows = session.scalars(
        select(EntityTag.tag)
        .where(EntityTag.entity_type == entity_type, EntityTag.entity_id == entity_id)
        .order_by(EntityTag.tag)
    ).all()
    return list(rows)


def has_tag(session: Session, entity_type: str, entity_id: int, tag: str) -> bool:
    return (
        session.scalar(
            select(EntityTag.id).where(
                EntityTag.entity_type == entity_type,
                EntityTag.entity_id == entity_id,
                EntityTag.tag == tag,
            )
        )
        is not None
    )


def has_protected_tag(session: Session, entity_type: str, entity_id: int) -> bool:
    return has_tag(session, entity_type, entity_id, PROTECTED_TAG)


def set_tags(session: Session, entity_type: str, entity_id: int, tags: list[str]) -> list[str]:
    clean = sorted({t.strip() for t in tags if t and t.strip()})
    session.execute(
        delete(EntityTag).where(
            EntityTag.entity_type == entity_type,
            EntityTag.entity_id == entity_id,
        )
    )
    for tag in clean:
        session.add(EntityTag(entity_type=entity_type, entity_id=entity_id, tag=tag))
    session.commit()
    return clean


def add_tag(session: Session, entity_type: str, entity_id: int, tag: str) -> None:
    tag = tag.strip()
    if not tag:
        return
    if has_tag(session, entity_type, entity_id, tag):
        return
    session.add(EntityTag(entity_type=entity_type, entity_id=entity_id, tag=tag))
    session.commit()


def remove_tag(session: Session, entity_type: str, entity_id: int, tag: str) -> None:
    session.execute(
        delete(EntityTag).where(
            EntityTag.entity_type == entity_type,
            EntityTag.entity_id == entity_id,
            EntityTag.tag == tag.strip(),
        )
    )
    session.commit()


def suggest_tags(session: Session, *, prefix: str = "") -> list[str]:
    q = select(EntityTag.tag).distinct().order_by(EntityTag.tag)
    if prefix:
        q = q.where(EntityTag.tag.ilike(f"{prefix}%"))
    return list(session.scalars(q.limit(50)).all())


def entity_ids_with_tag(session: Session, entity_type: str, tag: str) -> list[int]:
    return list(
        session.scalars(
            select(EntityTag.entity_id).where(
                EntityTag.entity_type == entity_type,
                EntityTag.tag == tag,
            )
        ).all()
    )
