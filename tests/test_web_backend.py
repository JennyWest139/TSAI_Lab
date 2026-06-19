"""Tests fuer Flask-Web-Backend (Mock-Modus)."""

from __future__ import annotations

import unittest

from tslab.web.app import create_app
from tslab.web.backend import WebBackend


class WebBackendMockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = WebBackend(use_mock=True)
        app = create_app(use_mock=True)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_probe_db_retries_after_failure(self) -> None:
        backend = WebBackend(use_mock=False)
        backend._db_ok = False  # simuliert alten Bug: dauerhaft False
        # Ohne Fix bliebe uses_mock True; mit Fix wird neu probiert
        if backend._probe_db():
            self.assertFalse(backend.uses_mock)
            self.assertTrue(backend._db_ok)

    def test_mock_backend_lists_series(self) -> None:
        series = self.backend.list_series()
        self.assertGreaterEqual(len(series), 3)
        self.assertTrue(any(s.slug == "pdax" for s in series))

    def test_mock_pair_overlap(self) -> None:
        data = self.backend.pair_overlap("pdax", "dax")
        self.assertIsNotNone(data)
        assert data is not None
        self.assertIn("overlap_start", data)
        self.assertGreater(data["overlap_observations"], 0)

    def test_mock_correlation_run(self) -> None:
        result = self.backend.run_correlation(
            {"series_a": "pdax", "series_b": "dax", "analysis_mode": "thesis", "max_lag": "12"}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "simulated")

    def test_mock_tsa_run(self) -> None:
        result = self.backend.run_tsa(
            {
                "series_slug": "pdax",
                "analysis_mode": "thesis",
                "train_start": "1987-12-01",
                "train_end": "2006-07-01",
                "forecast_end": "2008-07-01",
                "models": ["arma-garch"],
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "simulated")

    def test_api_series(self) -> None:
        res = self.client.get("/api/series")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertTrue(any(s["slug"] == "pdax" for s in data))

    def test_api_overlap(self) -> None:
        res = self.client.get("/api/overlap?a=pdax&b=dax")
        self.assertEqual(res.status_code, 200)
        self.assertIn("suggested_start", res.get_json())

    def test_api_correlation_run_mock(self) -> None:
        res = self.client.post(
            "/api/correlation/run",
            json={
                "series_a": "pdax",
                "series_b": "dax",
                "analysis_mode": "thesis",
                "max_lag": 24,
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["ok"])

    def test_api_tsa_run_mock(self) -> None:
        res = self.client.post(
            "/api/tsa/run",
            json={
                "series_slug": "pdax",
                "analysis_mode": "thesis",
                "train_start": "1987-12-01",
                "train_end": "2006-07-01",
                "forecast_end": "2008-07-01",
                "models": ["garch"],
                "plot_pre_years": 3,
                "plot_forecast_years": 1,
                "plot_post_years": 1,
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "simulated")

    def test_dashboard_renders(self) -> None:
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Backend:", res.data)
        self.assertIn(b"btn-help", res.data)

    def test_manual_pdf_available(self) -> None:
        res = self.client.get("/static/docs/tslab_benutzerhandbuch.pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/pdf")

    def test_series_detail_page(self) -> None:
        res = self.client.get("/series/pdax")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"seriesChart", res.data)
        self.assertIn(b"plotly", res.data)

    def test_api_series_chart(self) -> None:
        res = self.client.get("/api/series/pdax/chart")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["slug"], "pdax")
        self.assertGreater(len(data["dates"]), 0)

    def test_api_correlation_preview(self) -> None:
        res = self.client.get(
            "/api/correlation/preview?a=pdax&b=dax&start=1987-12-01&end=2006-07-01"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("series_a", data)
        self.assertIn("series_b", data)


if __name__ == "__main__":
    unittest.main()
