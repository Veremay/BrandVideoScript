import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent_llm import invoke_agent_json
from app.services.llm_errors import LLMInvocationError


class InvokeAgentJsonTests(unittest.IsolatedAsyncioTestCase):
    async def test_raises_when_llm_call_fails_with_api_key(self) -> None:
        client = MagicMock()
        client.settings.siliconflow_api_key = "test-key"
        client.complete_json_via_stream = AsyncMock(side_effect=ConnectionError("network down"))

        with patch("app.services.agent_llm.LLMClient", return_value=client):
            with self.assertRaises(LLMInvocationError):
                await invoke_agent_json(
                    agent_prompt_file="expert_agent.md",
                    context="ctx",
                    task_type="expert_generate_hunks",
                    mock_payload=lambda: {"ok": True},
                )

    async def test_uses_mock_when_api_key_missing(self) -> None:
        client = MagicMock()
        client.settings.siliconflow_api_key = ""

        with patch("app.services.agent_llm.LLMClient", return_value=client):
            result = await invoke_agent_json(
                agent_prompt_file="expert_agent.md",
                context="ctx",
                task_type="expert_generate_hunks",
                mock_payload=lambda: {"ok": True},
            )

        self.assertEqual(result, {"ok": True})


if __name__ == "__main__":
    unittest.main()
