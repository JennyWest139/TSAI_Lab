"""Tests fuer OpenAI-Provider (GPT-4o-mini Aufruf)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tslab.services.ai_providers import OpenAIProvider


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


if __name__ == "__main__":
    unittest.main()
