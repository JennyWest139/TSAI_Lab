"""Tests fuer Lauf-Telemetrie und KI-Session-Merge."""

from __future__ import annotations

from tslab.services.run_telemetry import RunTelemetryCollector


def test_merge_ai_session_result_sets_tokens_once_from_session():
    collector = RunTelemetryCollector(run_type="Korrelation")
    collector.merge_ai_session_result(
        {
            "token_usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 300,
                "total_tokens": 1500,
                "calls": 4,
                "model": "GPT-4o mini",
            },
            "reports": [
                {
                    "report_url": "/output/file/run/CORR_AI_Bericht_20260619_GPT4o_mini.docx",
                    "report_rel": "CORR_AI_Bericht_20260619_GPT4o_mini.docx",
                    "token_usage": {"prompt_tokens": 600, "completion_tokens": 150, "calls": 2},
                }
            ],
        }
    )
    assert collector.data.tokens.calls == 4
    assert collector.data.tokens.prompt_tokens == 1200
    assert collector.data.tokens.completion_tokens == 300
    assert collector.data.tokens.total_tokens == 1500
    assert collector.data.tokens.models == ["GPT-4o mini"]
    assert any("CORR AI-Bericht" in label for label in collector.data.links)


def test_merge_ai_session_result_without_reports_still_records_tokens():
    collector = RunTelemetryCollector(run_type="TSA")
    collector.merge_ai_session_result(
        {
            "token_usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
                "calls": 1,
                "model": "Gemini 2.5 Flash",
            }
        }
    )
    assert collector.data.tokens.calls == 1
    assert collector.data.tokens.total_tokens == 60


def test_merge_ai_reports_does_not_double_count_tokens():
    collector = RunTelemetryCollector(run_type="TSA")
    collector.merge_ai_session_result(
        {
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "calls": 2,
                "model": "GPT-4o mini",
            },
            "reports": [
                {
                    "report_url": "/output/file/a.docx",
                    "report_rel": "arma11/TSA_Modell_Bericht_20260619_GPT4o_mini.docx",
                    "token_usage": {"prompt_tokens": 50, "completion_tokens": 10, "calls": 1},
                },
                {
                    "report_url": "/output/file/b.docx",
                    "report_rel": "Reports/Modellvergleich_GPT4o_mini.docx",
                    "token_usage": {"prompt_tokens": 50, "completion_tokens": 10, "calls": 1},
                },
            ],
        }
    )
    assert collector.data.tokens.calls == 2
    assert collector.data.tokens.total_tokens == 120
    assert any("Modellvergleich" in label for label in collector.data.links)
    assert any("TSA Modell-Bericht" in label for label in collector.data.links)
