"""Tests fuer KI-Modellliste in der UI."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tslab.services.report_service import list_report_models, load_report_config


class ReportModelsListTests(unittest.TestCase):
    def test_default_models_four_enabled(self) -> None:
        cfg = load_report_config()
        enabled = [m for m in cfg.models if m.enabled]
        self.assertEqual(len(enabled), 4)
        labels = {m.label for m in enabled}
        self.assertEqual(
            labels,
            {"GPT-4o mini", "GPT-5 mini", "GPT-5 nano", "Gemini"},
        )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    def test_list_shows_all_with_availability(self) -> None:
        models = list_report_models()
        self.assertEqual(len(models), 4)
        self.assertTrue(all(m["available"] for m in models if m["provider"] == "openai"))
        gemini = next(m for m in models if m["provider"] == "gemini")
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
        self.assertEqual(len(models), 4)
        self.assertTrue(all(not m["available"] for m in models))


if __name__ == "__main__":
    unittest.main()
