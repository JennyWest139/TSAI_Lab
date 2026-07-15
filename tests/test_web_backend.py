"""Tests fuer Flask-Web-Backend (PostgreSQL erforderlich)."""

from __future__ import annotations

import unittest

from tslab.db.engine import DatabaseConnectionError, check_connection
from tslab.web.app import create_app
from tslab.web.backend import WebBackend


def _pg_available() -> bool:
    try:
        check_connection()
        return True
    except Exception:
        return False


@unittest.skipUnless(_pg_available(), "PostgreSQL nicht erreichbar")
class WebBackendPgTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = WebBackend()
        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_backend_lists_series(self) -> None:
        series = self.backend.list_series()
        self.assertIsInstance(series, list)

    def test_api_series(self) -> None:
        res = self.client.get("/api/series")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.get_json(), list)

    def test_api_backend_status(self) -> None:
        res = self.client.get("/api/backend/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["database_kind"], "postgresql")
        self.assertNotIn("uses_mock", data)

    def test_dashboard_renders(self) -> None:
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Backend:", res.data)
        self.assertNotIn(b"Mock-Modus", res.data)

    def test_manual_pdf_available(self) -> None:
        res = self.client.get("/static/docs/tslab_benutzerhandbuch.pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/pdf")


class WebBackendConstructorTests(unittest.TestCase):
    def test_create_app_requires_db_when_unreachable(self) -> None:
        """Ohne erreichbare DB schlaegt WebBackend() fehl (kein Mock-Fallback)."""
        if _pg_available():
            self.skipTest("PostgreSQL erreichbar — Fail-Fast-Pfad hier nicht testbar")
        with self.assertRaises((DatabaseConnectionError, ConnectionError, OSError)):
            WebBackend()


if __name__ == "__main__":
    unittest.main()
