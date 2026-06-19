"""Kategorien fuer Zeitreihen."""

from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from tslab.db.models import Category, TimeSeries

PROTECTED_CATEGORY = "Reporting"


def list_categories(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).order_by(Category.name)).all())


def get_category(session: Session, category_id: int) -> Category | None:
    return session.get(Category, category_id)


def get_category_by_name(session: Session, name: str) -> Category | None:
    return session.scalar(select(Category).where(func.lower(Category.name) == name.strip().lower()))


def seed_default_categories(session: Session) -> Category | None:
    """Legt geschuetzte Standard-Kategorie an."""
    existing = get_category_by_name(session, PROTECTED_CATEGORY)
    if existing:
        return existing
    row = Category(name=PROTECTED_CATEGORY)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def is_protected_category(category: Category | None) -> bool:
    return category is not None and category.name.strip().lower() == PROTECTED_CATEGORY.lower()


def series_has_protected_category(session: Session, series_id: int) -> bool:
    ts = session.get(TimeSeries, series_id)
    if ts is None or ts.category_id is None:
        return False
    cat = get_category(session, ts.category_id)
    return is_protected_category(cat)


def create_category(session: Session, name: str) -> Category:
    clean = name.strip()
    if not clean:
        raise ValueError("Kategoriename darf nicht leer sein.")
    if clean.lower() == PROTECTED_CATEGORY.lower():
        raise ValueError(f"Kategorie '{PROTECTED_CATEGORY}' ist reserviert.")
    if get_category_by_name(session, clean):
        raise ValueError(f"Kategorie '{clean}' existiert bereits.")
    row = Category(name=clean)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_category(session: Session, category_id: int, name: str) -> Category:
    row = get_category(session, category_id)
    if row is None:
        raise ValueError("Kategorie nicht gefunden.")
    clean = name.strip()
    if not clean:
        raise ValueError("Kategoriename darf nicht leer sein.")
    other = get_category_by_name(session, clean)
    if other is not None and other.id != category_id:
        raise ValueError(f"Kategorie '{clean}' existiert bereits.")
    row.name = clean
    session.commit()
    session.refresh(row)
    return row


def delete_category(session: Session, category_id: int) -> None:
    row = get_category(session, category_id)
    if row is None:
        raise ValueError("Kategorie nicht gefunden.")
    if is_protected_category(row):
        raise ValueError(f"Kategorie '{PROTECTED_CATEGORY}' darf nicht gelöscht werden.")
    session.execute(
        update(TimeSeries).where(TimeSeries.category_id == category_id).values(category_id=None)
    )
    session.delete(row)
    session.commit()


def assign_series_category(
    session: Session, series_id: int, category_id: int | None
) -> None:
    ts = session.get(TimeSeries, series_id)
    if ts is None:
        raise ValueError("Zeitreihe nicht gefunden.")
    if category_id is not None and get_category(session, category_id) is None:
        raise ValueError("Kategorie nicht gefunden.")
    ts.category_id = category_id
    session.commit()


def series_ids_for_category(session: Session, category_id: int) -> list[int]:
    return list(
        session.scalars(
            select(TimeSeries.id).where(TimeSeries.category_id == category_id)
        ).all()
    )
