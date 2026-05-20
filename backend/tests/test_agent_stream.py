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


def _audience_project_stub() -> dict:
    project = _project_stub()
    project["personas"] = [
        {
            "persona_id": "persona_1",
            "name": "年轻职场人",
            "ad_sensitivity": "medium",
            "trust_trigger": ["真实通勤场景"],
            "reject_trigger": ["硬广独白"],
        }
    ]
    project["active_persona_id"] = "persona_1"
    project["current_script"] = {
        "columns": [],
        "rows": [
            {"row_id": "row_1", "order": 0, "cells": []},
            {"row_id": "row_2", "order": 1, "cells": []},
        ],
        "updated_at": "2026-05-19T00:00:00+00:00",
    }
    return project


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

    async def _collect_audience(
        self, chunks: list[str], *, project: dict | None = None
    ) -> tuple[list[str], AsyncMock]:
        from app.services.agent_stream import stream_agent_response

        fake_stream = _FakeStream(chunks)
        save_analysis_mock = AsyncMock(return_value=_audience_project_stub())
        stub_project = project if project is not None else _audience_project_stub()
        with (
            patch("app.services.agent_stream.get_project", new=AsyncMock(return_value=stub_project)),
            patch("app.services.agent_stream.list_agent_messages", new=AsyncMock(return_value=[])),
            patch(
                "app.services.agent_stream.create_agent_message",
                new=AsyncMock(return_value={"_id": "msg_audience"}),
            ),
            patch("app.services.agent_stream.save_audience_analysis", new=save_analysis_mock),
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
                    agent_type="audience",
                    content="Q",
                    quotes=[],
                )
            ]
        return events, save_analysis_mock

    async def test_audience_agent_persists_analysis_artifact(self):
        chunks = [
            "以 年轻职场人 的视角，",
            "整体可信度可接受。\n\n",
            "<audience_analysis>",
            '{"summary":"中段广告感稍重",',
            '"naturalness_score":3,"credibility_score":4,"ad_sensitivity_score":4,',
            '"key_risks":["品牌口播过早"],',
            '"liked_parts":[{"row_id":"row_1","reason":"具体可信"}],',
            '"rejected_parts":[{"row_id":"row_2","reason":"转折生硬"}],',
            '"suggestions":["把形容词替换为数字"]}',
            "</audience_analysis>",
        ]
        events, save_analysis = await self._collect_audience(chunks)

        token_events = [e for e in events if e.startswith("event: token")]
        token_text = "".join(json.loads(e.split("data: ", 1)[1])["content"] for e in token_events)
        self.assertIn("年轻职场人", token_text)
        self.assertNotIn("audience_analysis", token_text)
        self.assertNotIn("naturalness_score", token_text)

        artifact_event = next(e for e in events if e.startswith("event: artifact"))
        artifact_payload = json.loads(artifact_event.split("data: ", 1)[1])
        self.assertEqual(artifact_payload["type"], "audience_analysis")
        self.assertEqual(artifact_payload["persona_id"], "persona_1")
        self.assertEqual(artifact_payload["persisted"], True)
        analysis = artifact_payload["analysis"]
        self.assertEqual(analysis["naturalness_score"], 3)
        self.assertEqual(analysis["liked_parts"][0]["row_id"], "row_1")
        save_analysis.assert_awaited_once()

        done_event = next(e for e in events if e.startswith("event: done"))
        done_payload = json.loads(done_event.split("data: ", 1)[1])
        self.assertEqual(done_payload["analysis_persisted"], True)
        self.assertEqual(done_payload["message_id"], "msg_audience")

    async def test_audience_agent_without_marker_skips_persist(self):
        chunks = ["以 年轻职场人 的视角，", "这段还需要再讨论。"]
        events, save_analysis = await self._collect_audience(chunks)
        self.assertFalse(any(e.startswith("event: artifact") for e in events))
        save_analysis.assert_not_awaited()
        done_event = next(e for e in events if e.startswith("event: done"))
        done_payload = json.loads(done_event.split("data: ", 1)[1])
        self.assertEqual(done_payload["analysis_persisted"], False)

    async def test_audience_agent_without_active_persona_returns_error(self):
        project = _audience_project_stub()
        project["active_persona_id"] = None
        project["personas"] = []
        events, save_analysis = await self._collect_audience(["..."], project=project)
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].startswith("event: error"))
        save_analysis.assert_not_awaited()

    async def _collect_expert(
        self,
        chunks: list[str],
        *,
        project: dict | None = None,
    ) -> tuple[list[str], AsyncMock]:
        from app.services.agent_stream import stream_agent_response

        fake_stream = _FakeStream(chunks)
        save_suggestions_mock = AsyncMock(return_value=_expert_project_stub())
        stub_project = project if project is not None else _expert_project_stub()
        with (
            patch("app.services.agent_stream.get_project", new=AsyncMock(return_value=stub_project)),
            patch("app.services.agent_stream.list_agent_messages", new=AsyncMock(return_value=[])),
            patch(
                "app.services.agent_stream.create_agent_message",
                new=AsyncMock(return_value={"_id": "msg_expert"}),
            ),
            patch(
                "app.services.agent_stream.save_expert_suggestions",
                new=save_suggestions_mock,
            ),
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
                    agent_type="expert",
                    content="给我两个修改方向",
                    quotes=[],
                )
            ]
        return events, save_suggestions_mock

    async def test_expert_agent_persists_suggestions_artifact(self):
        chunks = [
            "本轮聚焦中段广告感，",
            "提供 1 个方案。\n\n",
            "<expert_suggestions>",
            '{"items":[{"title":"强化真实感","direction":"balanced",',
            '"description":"用具体细节替换抽象表达","target_problem":"广告感偏强",',
            '"rationale":"audience score 4","brand_tradeoff":"卖点不变",',
            '"audience_tradeoff":"提升可信度","creator_tradeoff":"需要补充细节",',
            '"risk":"细节若不真实易被识别","explanation_to_brand":"用具体细节解释卖点",',
            '"hunks":[{"row_id":"row_1","column_id":"col_scene",',
            '"old":"原始画面","new":"上班通勤场景下的画面","reason":"用具体场景"}]}]}',
            "</expert_suggestions>",
        ]
        events, save_suggestions = await self._collect_expert(chunks)

        token_text = "".join(
            json.loads(e.split("data: ", 1)[1])["content"]
            for e in events
            if e.startswith("event: token")
        )
        self.assertIn("中段广告感", token_text)
        self.assertNotIn("expert_suggestions", token_text)
        self.assertNotIn("brand_tradeoff", token_text)

        artifact_event = next(e for e in events if e.startswith("event: artifact"))
        artifact_payload = json.loads(artifact_event.split("data: ", 1)[1])
        self.assertEqual(artifact_payload["type"], "expert_suggestions")
        self.assertEqual(artifact_payload["persisted_count"], 1)
        items = artifact_payload["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "强化真实感")
        self.assertEqual(items[0]["hunks"][0]["row_id"], "row_1")
        self.assertTrue(items[0]["hunks"][0]["hunk_id"].startswith("hunk_"))

        save_suggestions.assert_awaited_once()
        call_kwargs = save_suggestions.await_args.kwargs
        self.assertEqual(call_kwargs["based_on_brand_insight_ids"], [])
        self.assertIsNone(call_kwargs["based_on_audience_analysis_id"])

        done_event = next(e for e in events if e.startswith("event: done"))
        done_payload = json.loads(done_event.split("data: ", 1)[1])
        self.assertEqual(done_payload["suggestions_persisted_count"], 1)
        self.assertEqual(done_payload["message_id"], "msg_expert")

    async def test_expert_agent_drops_hunk_with_mismatched_old(self):
        chunks = [
            "正文内容。\n\n",
            "<expert_suggestions>",
            '{"items":[{"title":"无效方案","direction":"balanced","description":"d",',
            '"target_problem":"t","rationale":"r","brand_tradeoff":"b",',
            '"audience_tradeoff":"a","creator_tradeoff":"c","risk":"risk",',
            '"explanation_to_brand":"exp",',
            '"hunks":[{"row_id":"row_1","column_id":"col_scene",',
            '"old":"完全不一致的旧文","new":"新文","reason":"x"}]}]}',
            "</expert_suggestions>",
        ]
        events, save_suggestions = await self._collect_expert(chunks)
        self.assertFalse(any(e.startswith("event: artifact") for e in events))
        save_suggestions.assert_not_awaited()
        done_event = next(e for e in events if e.startswith("event: done"))
        done_payload = json.loads(done_event.split("data: ", 1)[1])
        self.assertEqual(done_payload["suggestions_persisted_count"], 0)

    async def test_expert_agent_without_marker_skips_persist(self):
        chunks = ["我先帮你分析一下问题，", "等你确认后再生成方案。"]
        events, save_suggestions = await self._collect_expert(chunks)
        self.assertFalse(any(e.startswith("event: artifact") for e in events))
        save_suggestions.assert_not_awaited()


def _expert_project_stub() -> dict:
    project = _project_stub()
    project["current_script"] = {
        "columns": [
            {"column_id": "col_duration", "label": "时长", "type": "duration", "multiline": False, "order": 0},
            {"column_id": "col_scene", "label": "画面", "type": "textarea", "multiline": True, "order": 1},
            {"column_id": "col_notes", "label": "备注", "type": "text", "multiline": False, "order": 2},
        ],
        "rows": [
            {
                "row_id": "row_1",
                "order": 0,
                "cells": [
                    {"column_id": "col_duration", "value": "0-5"},
                    {"column_id": "col_scene", "value": "原始画面"},
                    {"column_id": "col_notes", "value": "原始备注"},
                ],
            },
        ],
        "updated_at": "2026-05-19T00:00:00+00:00",
    }
    project["expert_suggestions"] = []
    project["brand_insights"] = []
    project["audience_analysis"] = {}
    return project


if __name__ == "__main__":
    unittest.main()
