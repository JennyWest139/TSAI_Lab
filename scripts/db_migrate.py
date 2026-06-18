"""CLI: Schema-Migration ausfuehren."""

from __future__ import annotations

from tslab.db.migrate import migrate_schema

if __name__ == "__main__":
    migrate_schema()
    print("Schema migration complete.")
