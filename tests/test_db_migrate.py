"""Tests fuer Schema-Migration (hidden_at u. a.)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select

# SQLite-Test-DB vor Engine-Import setzen
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["TSLAB_DATABASE_URL"] = f"sqlite:///{Path(_tmp.name).as_posix()}"
os.environ.pop("TSLAB_USE_SQLITE", None)

from tslab.db.engine import get_engine, get_session, init_db  # noqa: E402
from tslab.db.migrate import migrate_columns  # noqa: E402
from tslab.db.models import TimeSeries  # noqa: E402


class SchemaMigrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Alte Engine-Instanz aus Cache entfernen
        import tslab.db.engine as eng

        eng._engines.clear()
        init_db()

    def test_hidden_at_column_exists(self) -> None:
        cols = {c["name"] for c in inspect_columns("time_series")}
        self.assertIn("hidden_at", cols)

    def test_query_time_series_with_hidden_at(self) -> None:
        with get_session() as session:
            session.add(
                TimeSeries(
                    name="migrate_test",
                    slug="migrate_test",
                    observation_count=0,
                )
            )
            session.commit()
            row = session.scalar(select(TimeSeries).where(TimeSeries.slug == "migrate_test"))
            assert row is not None
            self.assertIsNone(row.hidden_at)

    def test_migrate_columns_idempotent(self) -> None:
        again = migrate_columns()
        self.assertEqual(again, [])


def inspect_columns(table: str) -> list:
    from sqlalchemy import inspect as sa_inspect

    return sa_inspect(get_engine()).get_columns(table)


if __name__ == "__main__":
    unittest.main()
