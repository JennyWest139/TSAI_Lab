"""Tests fuer KI-Modellliste in der UI."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tslab.services.report_service import list_report_models, load_report_config

_GEMINI_LABELS = (
    "Gemini 3.1 Flash Lite",
    "Gemini 2.5 Flash Lite",
    "Gemini 2.5 Flash",
)


class ReportModelsListTests(unittest.TestCase):
    def test_default_models_six_enabled(self) -> None:
        cfg = load_report_config()
        enabled = [m for m in cfg.models if m.enabled]
        self.assertEqual(len(enabled), 6)
        labels = [m.label for m in enabled if m.provider == "gemini"]
        self.assertEqual(labels, list(_GEMINI_LABELS))

    def test_gemini_models_ordered_before_25_flash(self) -> None:
        models = list_report_models()
        gemini_ids = [m["id"] for m in models if m["provider"] == "gemini"]
        self.assertEqual(
            gemini_ids,
            [
                "gemini:gemini-3.1-flash-lite",
                "gemini:gemini-2.5-flash-lite",
                "gemini:gemini-2.5-flash",
            ],
        )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    def test_list_shows_all_with_availability(self) -> None:
        models = list_report_models()
        self.assertEqual(len(models), 6)
        self.assertTrue(all(m["available"] for m in models if m["provider"] == "openai"))
        for gemini in (m for m in models if m["provider"] == "gemini"):
            self.assertFalse(gemini["available"])

    def test_list_shows_unavailable_without_key(self) -> None:
        env = os.environ.copy()
        try:
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("GEMINI_API_KEY", None)
            models = list_report_models()
        finally:
            os.environ.clear()
            os.environ.update(env)
        self.assertEqual(len(models), 6)
        self.assertTrue(all(not m["available"] for m in models))


if __name__ == "__main__":
    unittest.main()
