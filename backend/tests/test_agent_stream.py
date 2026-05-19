import unittest
from unittest.mock import AsyncMock, patch

from app.services.sse import encode_sse


class AgentStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_stream_agent_response_returns_error_when_project_is_missing(self):
        from app.services.agent_stream import stream_agent_response

        with patch("app.services.agent_stream.get_project", new=AsyncMock(return_value=None)):
            events = [
                event
                async for event in stream_agent_response(
                    AsyncMock(),
                    project_id="missing",
                    user_id="user_1",
                    agent_type="brand",
                    content="Hello",
                    quotes=[],
                )
            ]

        self.assertEqual(events, [encode_sse("error", {"message": "Project not found"})])


if __name__ == "__main__":
    unittest.main()
