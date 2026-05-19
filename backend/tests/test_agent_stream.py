import json
import unittest
from unittest.mock import AsyncMock, patch

from app.services.sse import encode_sse


def _project_stub() -> dict:
    return {
        "_id": "p1",
        "user_id": "u1",
        "brief": {"summary": "x"},
        "current_script": {"columns": [], "rows": []},
        "brand_insights": [],
        "brand_research": {"entity": {}, "research_summary": ""},
        "personas": [],
        "active_persona_id": None,
        "audience_analysis": {},
    }


class _FakeStream:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    def __call__(self, *args, **kwargs):
        async def gen():
            for c in self._chunks:
                yield c

        return gen()


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

    async def _collect(self, chunks: list[str]) -> tuple[list[str], AsyncMock]:
        from app.services.agent_stream import stream_agent_response

        fake_stream = _FakeStream(chunks)
        create_insight_mock = AsyncMock(return_value=_project_stub())
        with (
            patch("app.services.agent_stream.get_project", new=AsyncMock(return_value=_project_stub())),
            patch("app.services.agent_stream.list_agent_messages", new=AsyncMock(return_value=[])),
            patch(
                "app.services.agent_stream.create_agent_message",
                new=AsyncMock(return_value={"_id": "msg_1"}),
            ),
            patch("app.services.agent_stream.create_brand_insight", new=create_insight_mock),
            patch("app.services.agent_stream.PromptLoader") as MockLoader,
            patch("app.services.agent_stream.LLMClient") as MockClient,
        ):
            MockLoader.return_value.render.return_value = "system"
            MockClient.return_value.stream_chat = fake_stream
            events = [
                event
                async for event in stream_agent_response(
                    AsyncMock(),
                    project_id="p1",
                    user_id="u1",
                    agent_type="brand",
                    content="Q",
                    quotes=[],
                )
            ]
        return events, create_insight_mock

    async def test_brand_agent_emits_artifact_and_strips_marker_from_text(self):
        chunks = [
            "对脚本的反馈：节奏",
            "可以再放慢。\n\n",
            "<brand_insight_proposals>",
            '{"items":[{"category":"implicit_requirement","title":"保持留白",',
            '"content":"镜头节奏放慢","confidence":"medium",',
            '"evidence":[{"source_type":"brand_wiki","quote":"留白感"}]}]}',
            "</brand_insight_proposals>",
        ]
        events, create_insight = await self._collect(chunks)

        token_events = [e for e in events if e.startswith("event: token")]
        token_text = "".join(json.loads(e.split("data: ", 1)[1])["content"] for e in token_events)
        self.assertIn("放慢", token_text)
        self.assertNotIn("brand_insight_proposals", token_text)
        self.assertNotIn("implicit_requirement", token_text)

        artifact_event = next(e for e in events if e.startswith("event: artifact"))
        artifact_payload = json.loads(artifact_event.split("data: ", 1)[1])
        self.assertEqual(artifact_payload["type"], "brand_insight_proposals")
        self.assertEqual(len(artifact_payload["items"]), 1)
        self.assertEqual(artifact_payload["items"][0]["category"], "implicit_requirement")
        self.assertEqual(artifact_payload["persisted_count"], 1)

        create_insight.assert_awaited_once()
        kwargs = create_insight.await_args.kwargs
        self.assertEqual(kwargs["category"], "implicit_requirement")
        self.assertEqual(kwargs["status"], "new")
        self.assertEqual(kwargs["created_by"], "agent")

        done_event = next(e for e in events if e.startswith("event: done"))
        done_payload = json.loads(done_event.split("data: ", 1)[1])
        self.assertEqual(done_payload["proposal_count"], 1)
        self.assertEqual(done_payload["persisted_count"], 1)
        self.assertEqual(done_payload["message_id"], "msg_1")

    async def test_brand_agent_handles_typo_closing_marker_in_stream(self):
        # Simulate the real LLM typo observed in production: `</brand_insights_proposals>`.
        chunks = [
            "正文反馈...\n\n",
            "<brand_insight_proposals>\n",
            '{"items":[{"category":"brand_feedback","title":"T","content":"C",',
            '"confidence":"low","evidence":[{"source_type":"chat","quote":"q"}]}]}',
            "\n</brand_insights_proposals>",
        ]
        events, create_insight = await self._collect(chunks)
        token_text = "".join(
            json.loads(e.split("data: ", 1)[1])["content"]
            for e in events
            if e.startswith("event: token")
        )
        self.assertNotIn("brand_insight_proposals", token_text)
        self.assertNotIn("brand_insights_proposals", token_text)
        self.assertNotIn("brand_feedback", token_text)

        artifact_event = next(e for e in events if e.startswith("event: artifact"))
        artifact_payload = json.loads(artifact_event.split("data: ", 1)[1])
        self.assertEqual(artifact_payload["persisted_count"], 1)
        create_insight.assert_awaited_once()

    async def test_brand_agent_without_marker_streams_full_text(self):
        chunks = ["对脚本的", "整体反馈：节奏OK"]
        events, create_insight = await self._collect(chunks)
        token_events = [e for e in events if e.startswith("event: token")]
        token_text = "".join(json.loads(e.split("data: ", 1)[1])["content"] for e in token_events)
        self.assertEqual(token_text, "对脚本的整体反馈：节奏OK")
        self.assertFalse(any(e.startswith("event: artifact") for e in events))
        create_insight.assert_not_awaited()
        done_event = next(e for e in events if e.startswith("event: done"))
        done_payload = json.loads(done_event.split("data: ", 1)[1])
        self.assertEqual(done_payload["proposal_count"], 0)
        self.assertEqual(done_payload["persisted_count"], 0)


if __name__ == "__main__":
    unittest.main()
