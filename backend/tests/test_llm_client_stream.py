import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_client import LLMClient


class _FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamCM:
    def __init__(self, response: _FakeStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeStreamResponse:
        return self._response

    async def __aexit__(self, *args: object) -> None:
        return None


class StreamTokensEmptyChoicesTests(unittest.IsolatedAsyncioTestCase):
    async def test_skips_chunks_with_empty_choices(self) -> None:
        lines = [
            'data: {"id":"chunk-0","choices":[]}',
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            "data: [DONE]",
        ]
        fake_client = MagicMock()
        fake_client.stream.return_value = _FakeStreamCM(_FakeStreamResponse(lines))
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=None)

        settings = MagicMock()
        settings.siliconflow_api_key = "test-key"
        settings.siliconflow_base_url = "https://example.test"
        settings.siliconflow_stream_timeout_seconds = 30.0

        llm = LLMClient()
        with (
            patch.object(llm, "settings", settings),
            patch("app.services.llm_client.select_model", return_value="test-model"),
            patch("app.services.llm_client.should_enable_thinking", return_value=False),
            patch("app.services.llm_client.httpx.AsyncClient", return_value=fake_client),
            patch("app.services.llm_client.log_llm_request"),
            patch("app.services.llm_client.log_llm_response"),
        ):
            tokens = [
                token
                async for token in llm.stream_tokens(
                    messages=[{"role": "user", "content": "hi"}],
                    task_type="vanilla_chat",
                    mock=False,
                )
            ]

        self.assertEqual(tokens, ["Hello", " world"])
        # Ensure the empty-choices chunk was valid JSON (regression guard for parse path)
        self.assertEqual(json.loads(lines[0][5:].strip())["choices"], [])


if __name__ == "__main__":
    unittest.main()
