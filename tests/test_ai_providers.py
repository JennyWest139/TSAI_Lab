"""Tests fuer OpenAI- und Gemini-Provider."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tslab.services.ai_providers import GeminiProvider, OpenAIProvider


class OpenAIProviderTests(unittest.TestCase):
    def test_create_does_not_pass_legacy_name_kwarg(self) -> None:
        provider = OpenAIProvider("sk-test", config=None)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Antwort"))],
            usage=None,
        )
        provider._client_instance = mock_client
        provider._client_is_langfuse = False

        provider.complete_text(
            system="sys",
            user="usr",
            model="gpt-4o-mini",
            max_tokens=100,
            trace_name="tslab-test",
        )

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertNotIn("name", kwargs)
        self.assertEqual(kwargs.get("model"), "gpt-4o-mini")
        self.assertEqual(kwargs.get("metadata"), {"tslab_trace": "tslab-test"})


class GeminiProviderTests(unittest.TestCase):
    def test_complete_text_uses_system_instruction(self) -> None:
        provider = GeminiProvider("gem-test")
        mock_client = MagicMock()
        mock_usage = MagicMock(prompt_token_count=10, candidates_token_count=20, total_token_count=30)
        mock_client.models.generate_content.return_value = MagicMock(
            text="Gemini-Antwort",
            usage_metadata=mock_usage,
        )
        provider._client_instance = mock_client

        resp = provider.complete_text(
            system="sys",
            user="usr",
            model="gemini-2.0-flash",
            max_tokens=100,
            trace_name="tslab-test",
        )

        self.assertEqual(resp.text, "Gemini-Antwort")
        self.assertEqual(resp.usage.prompt_tokens, 10)
        kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-2.0-flash")
        self.assertEqual(kwargs["contents"], "usr")
        self.assertEqual(kwargs["config"].system_instruction, "sys")

    def test_describe_image_sends_bytes_part(self) -> None:
        provider = GeminiProvider("gem-test")
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock(
            text="Bildbeschreibung",
            usage_metadata=None,
        )
        provider._client_instance = mock_client

        with patch("pathlib.Path.read_bytes", return_value=b"png-bytes"):
            resp = provider.describe_image(
                image_path=Path("chart.png"),
                prompt="Beschreibe",
                model="gemini-2.0-flash",
                max_tokens=50,
                trace_name="img",
            )

        self.assertEqual(resp.text, "Bildbeschreibung")
        contents = mock_client.models.generate_content.call_args.kwargs["contents"]
        self.assertEqual(len(contents), 2)
        self.assertEqual(contents[1], "Beschreibe")


if __name__ == "__main__":
    unittest.main()
