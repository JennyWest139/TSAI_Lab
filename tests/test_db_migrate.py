"""Tests fuer Schema-Migration (PostgreSQL erforderlich)."""

from __future__ import annotations

import unittest

from sqlalchemy import select

from tslab.db.engine import check_connection, get_engine, get_session, init_db, reset_engine_cache
from tslab.db.migrate import migrate_columns
from tslab.db.models import TimeSeries


def _pg_available() -> bool:
    try:
        check_connection()
        return True
    except Exception:
        return False


@unittest.skipUnless(_pg_available(), "PostgreSQL nicht erreichbar")
class SchemaMigrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        reset_engine_cache()
        init_db()

    def test_hidden_at_column_exists(self) -> None:
        cols = {c["name"] for c in inspect_columns("time_series")}
        self.assertIn("hidden_at", cols)

    def test_query_time_series_with_hidden_at(self) -> None:
        slug = "migrate_test_p2"
        with get_session() as session:
            existing = session.scalar(select(TimeSeries).where(TimeSeries.slug == slug))
            if existing is None:
                session.add(
                    TimeSeries(
                        name="migrate_test_p2",
                        slug=slug,
                        observation_count=0,
                    )
                )
                session.commit()
            row = session.scalar(select(TimeSeries).where(TimeSeries.slug == slug))
            assert row is not None
            self.assertTrue(hasattr(row, "hidden_at"))

    def test_migrate_columns_idempotent(self) -> None:
        again = migrate_columns()
        self.assertEqual(again, [])


def inspect_columns(table: str) -> list:
    from sqlalchemy import inspect as sa_inspect

    return sa_inspect(get_engine()).get_columns(table)


if __name__ == "__main__":
    unittest.main()
