"""Tests fuer Delete-Service und Report-Stub."""

from __future__ import annotations

import unittest

from tslab.services.delete_service import PROTECTED_TAG
from tslab.services.report_service import generate_run_report, load_report_config


class DeleteServiceTests(unittest.TestCase):
    def test_protected_tag_constant(self) -> None:
        self.assertEqual(PROTECTED_TAG, "Reporting")


class ReportServiceTests(unittest.TestCase):
    def test_report_disabled_by_default(self) -> None:
        cfg = load_report_config()
        self.assertFalse(cfg.enabled)

    def test_generate_disabled_when_off(self) -> None:
        cfg = load_report_config()
        if cfg.enabled:
            self.skipTest("ai_reports enabled in environment")
        result = generate_run_report("output/nonexistent")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "disabled")


if __name__ == "__main__":
    unittest.main()
