import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.context_compress import (
    HISTORY_TOKEN_LIMIT,
    KEEP_RECENT_MESSAGES,
    maybe_compress_history,
)


class MaybeCompressHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_below_limit_returns_unchanged(self) -> None:
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        llm = MagicMock()
        result = await maybe_compress_history(messages, llm=llm)
        self.assertEqual(result, messages)
        llm.chat.assert_not_called()

    async def test_over_limit_keeps_recent_and_prepends_summary(self) -> None:
        old = [{"role": "user", "content": "old " * 2000} for _ in range(20)]
        recent = [
            {"role": "user", "content": "recent-user"},
            {"role": "assistant", "content": "recent-assistant"},
        ]
        # Pad recent to KEEP_RECENT_MESSAGES so split is deterministic
        while len(recent) < KEEP_RECENT_MESSAGES:
            recent.insert(0, {"role": "assistant", "content": f"keep-{len(recent)}"})
        messages = old + recent

        self.assertGreater(sum(len(m["content"]) for m in messages) // 2, HISTORY_TOKEN_LIMIT // 10)

        llm = MagicMock()
        llm.settings.siliconflow_api_key = "test-key"
        llm.chat = AsyncMock(return_value={"choices": [{"message": {"content": "SUMMARY_TEXT"}}]})
        llm._extract_message_content = MagicMock(return_value="SUMMARY_TEXT")

        with patch("app.services.context_compress.load_prompt", return_value="compress system"):
            result = await maybe_compress_history(messages, llm=llm, token_limit=100)

        self.assertEqual(result[0]["role"], "user")
        self.assertTrue(
            "SUMMARY_TEXT" in result[0]["content"]
            and ("对话摘要" in result[0]["content"] or "Conversation summary" in result[0]["content"])
        )
        self.assertEqual(result[1:], recent[-KEEP_RECENT_MESSAGES:])
        llm.chat.assert_awaited_once()

    async def test_compress_failure_hard_truncates_to_recent(self) -> None:
        messages = [{"role": "user", "content": "x" * 500} for _ in range(30)]
        llm = MagicMock()
        llm.settings.siliconflow_api_key = "test-key"
        llm.chat = AsyncMock(side_effect=RuntimeError("boom"))

        with patch("app.services.context_compress.load_prompt", return_value="compress system"):
            result = await maybe_compress_history(messages, llm=llm, token_limit=50)

        self.assertEqual(result, messages[-KEEP_RECENT_MESSAGES:])


if __name__ == "__main__":
    unittest.main()
