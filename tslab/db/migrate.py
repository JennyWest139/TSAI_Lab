"""Idempotente Schema-Migrationen (ohne Alembic)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, select, text

from tslab.db.engine import get_engine
from tslab.db.models import Base

_log = logging.getLogger(__name__)

# (table, column, postgres_ddl)
_COLUMN_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("time_series", "hidden_at", "hidden_at TIMESTAMPTZ"),
    ("correlation_history", "analysis_mode", "analysis_mode VARCHAR(32)"),
    ("correlation_history", "run_name", "run_name VARCHAR(256)"),
    ("correlation_history", "hidden_at", "hidden_at TIMESTAMPTZ"),
)


def _insp():
    return inspect(get_engine())


def _table_names() -> set[str]:
    return set(_insp().get_table_names())


def _column_names(table: str) -> set[str]:
    insp = _insp()
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_column_if_missing(table: str, column: str, ddl: str) -> bool:
    if column in _column_names(table):
        return False
    with get_engine().begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    _log.info("Schema migration: %s.%s added", table, column)
    return True


def migrate_columns() -> list[str]:
    """ALTER TABLE fuer fehlende Spalten an bestehenden Tabellen."""
    applied: list[str] = []
    for table, column, pg_ddl in _COLUMN_MIGRATIONS:
        if table not in _table_names():
            continue
        if _add_column_if_missing(table, column, pg_ddl):
            applied.append(f"{table}.{column}")
    return applied


def migrate_schema() -> None:
    """Neue Tabellen anlegen + fehlende Spalten nachziehen + Categories→Tags."""
    engine = get_engine()
    _migrate_categories_to_tags()
    Base.metadata.create_all(engine)
    migrate_columns()
    _seed_tags()
    _normalize_output_dirs()


def _drop_category_id_fk(conn) -> None:
    """Entfernt FK time_series.category_id falls vorhanden."""
    for fk in _insp().get_foreign_keys("time_series"):
        if list(fk.get("constrained_columns") or []) == ["category_id"]:
            name = fk.get("name")
            if name:
                conn.execute(text(f'ALTER TABLE time_series DROP CONSTRAINT IF EXISTS "{name}"'))


def _migrate_categories_to_tags() -> None:
    """Idempotent: categories/entity_categories → tags/entity_tag_links."""
    try:
        tables = _table_names()
        if not tables:
            return

        # 1) Orphan Freitext-Tabelle entity_tags droppen (Spalte tag, kein tag_id)
        if "entity_tags" in tables:
            cols = _column_names("entity_tags")
            if "tag" in cols and "tag_id" not in cols:
                with get_engine().begin() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS entity_tags CASCADE"))
                _log.info("Schema migration: orphan entity_tags dropped")
                tables = _table_names()

        # 2) categories → tags (+ Backfill, category_id drop)
        if "categories" in tables and "tags" not in tables:
            ts_cols = _column_names("time_series")
            with get_engine().begin() as conn:
                if "entity_categories" in tables and "category_id" in ts_cols:
                    conn.execute(
                        text(
                            """
                            INSERT INTO entity_categories (entity_type, entity_id, category_id)
                            SELECT 'series', ts.id, ts.category_id
                            FROM time_series ts
                            WHERE ts.category_id IS NOT NULL
                              AND NOT EXISTS (
                                SELECT 1 FROM entity_categories ec
                                WHERE ec.entity_type = 'series'
                                  AND ec.entity_id = ts.id
                                  AND ec.category_id = ts.category_id
                              )
                            """
                        )
                    )
                    _log.info("Schema migration: series category_id backfilled into entity_categories")
                if "category_id" in ts_cols:
                    _drop_category_id_fk(conn)
                    conn.execute(text("ALTER TABLE time_series DROP COLUMN IF EXISTS category_id"))
                    _log.info("Schema migration: time_series.category_id dropped")
                conn.execute(text("ALTER TABLE categories RENAME TO tags"))
                _log.info("Schema migration: categories renamed to tags")
            tables = _table_names()

        # 3) entity_categories → entity_tag_links (+ category_id → tag_id)
        if "entity_categories" in _table_names() and "entity_tag_links" not in _table_names():
            with get_engine().begin() as conn:
                conn.execute(text("ALTER TABLE entity_categories RENAME TO entity_tag_links"))
                _log.info("Schema migration: entity_categories renamed to entity_tag_links")
            link_cols = _column_names("entity_tag_links")
            if "category_id" in link_cols and "tag_id" not in link_cols:
                with get_engine().begin() as conn:
                    conn.execute(
                        text("ALTER TABLE entity_tag_links RENAME COLUMN category_id TO tag_id")
                    )
                    _log.info("Schema migration: entity_tag_links.category_id → tag_id")
            with get_engine().begin() as conn:
                for stmt in (
                    "ALTER INDEX IF EXISTS ix_entity_categories_cat RENAME TO ix_entity_tag_links_tag",
                    "ALTER INDEX IF EXISTS ix_entity_categories_entity RENAME TO ix_entity_tag_links_entity",
                    "ALTER TABLE entity_tag_links RENAME CONSTRAINT uq_entity_categories TO uq_entity_tag_links",
                ):
                    try:
                        conn.execute(text(stmt))
                    except Exception:
                        pass

        # 4) Rest category_id entfernen (falls Tags schon da)
        if "tags" in _table_names() and "category_id" in _column_names("time_series"):
            with get_engine().begin() as conn:
                _drop_category_id_fk(conn)
                conn.execute(text("ALTER TABLE time_series DROP COLUMN IF EXISTS category_id"))
            _log.info("Schema migration: leftover time_series.category_id dropped")

        # 5) Orphan entity_tags nach erfolgreicher Link-Tabelle
        if "entity_tag_links" in _table_names() and "entity_tags" in _table_names():
            cols = _column_names("entity_tags")
            if "tag" in cols and "tag_id" not in cols:
                with get_engine().begin() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS entity_tags CASCADE"))
                _log.info("Schema migration: leftover orphan entity_tags dropped")
    except Exception as exc:
        _log.warning("Categories→Tags Migration uebersprungen/fehlgeschlagen: %s", exc)


def _normalize_output_dirs() -> None:
    """Absolute output_dir-Werte in relative Verweise unter output/ umwandeln."""
    try:
        from sqlalchemy.orm import Session

        from tslab.db.models import CorrelationHistory, TsaHistory
        from tslab.services.output_paths import output_ref

        with Session(get_engine()) as session:
            changed = 0
            for row in session.scalars(select(CorrelationHistory)).all():
                if not row.output_dir:
                    continue
                try:
                    ref = output_ref(row.output_dir)
                except ValueError:
                    row.output_dir = None
                    changed += 1
                    continue
                if ref != row.output_dir:
                    row.output_dir = ref
                    changed += 1
            for row in session.scalars(select(TsaHistory)).all():
                if not row.output_dir:
                    continue
                try:
                    ref = output_ref(row.output_dir)
                except ValueError:
                    row.output_dir = None
                    changed += 1
                    continue
                if ref != row.output_dir:
                    row.output_dir = ref
                    changed += 1
            if changed:
                session.commit()
                _log.info("Schema migration: %s output_dir value(s) normalized", changed)
    except Exception as exc:
        _log.warning("Output-dir-Normalisierung uebersprungen: %s", exc)


def _seed_tags() -> None:
    try:
        from sqlalchemy.orm import Session

        from tslab.services.tag_service import seed_default_tags

        with Session(get_engine()) as session:
            seed_default_tags(session)
    except Exception as exc:
        _log.warning("Tag-Seed uebersprungen: %s", exc)
