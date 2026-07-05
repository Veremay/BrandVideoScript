import unittest
from unittest.mock import AsyncMock, patch

from app.repositories.coordinator_messages import build_coordinator_message
from app.services.agents.coordinator_agent import run_conflict_tagging
from app.services.coordinator_service import stream_graph_sync
from app.services.sse import encode_sse


class CoordinatorMessagesTest(unittest.TestCase):
    def test_build_coordinator_message_has_metadata(self) -> None:
        message = build_coordinator_message(
            project_id="project_1",
            user_id="user_1",
            role="user",
            content="What about this line?",
            task_type="quote_analysis",
            requested_perspectives=["brand", "audience"],
            quotes=[{"text": "hello", "row_id": "row_1"}],
            related_node_ids=["node_1"],
        )
        self.assertTrue(message["message_id"].startswith("msg_"))
        self.assertEqual(message["requested_perspectives"], ["brand", "audience"])
        self.assertEqual(message["quotes"][0]["row_id"], "row_1")


class SseEncodingTest(unittest.TestCase):
    def test_encode_sse_frame(self) -> None:
        frame = encode_sse("token", {"content": "hi"})
        self.assertIn("event: token", frame)
        self.assertIn('"content": "hi"', frame)


class CoordinatorConflictTaggingTest(unittest.IsolatedAsyncioTestCase):
    async def test_conflict_tagging_returns_decision_issues(self) -> None:
        position_a = {
            "node_id": "node_pos_a",
            "node_type": "position",
            "source_type": "brand_brief",
            "title": "品牌前三秒露出产品",
            "content": "品牌希望尽早传达卖点",
        }
        position_b = {
            "node_id": "node_pos_b",
            "node_type": "position",
            "source_type": "audience_simulation",
            "title": "观众需要自然开场",
            "content": "过早卖点会提高广告感",
        }
        payload = {
            "conflict_groups": [
                {
                    "tag": "A",
                    "relation_type": "conflict",
                    "reason": "露出时机取舍",
                    "position_ids": ["node_pos_a", "node_pos_b"],
                }
            ],
            "decision_issues": [
                {
                    "title": "品牌露出时机如何兼顾信息传达与自然感？",
                    "content": "多个立场都在回应同一露出时机决策。",
                    "position_ids": ["node_pos_a", "node_pos_b"],
                }
            ],
        }

        with patch(
            "app.services.agents.coordinator_agent.invoke_agent_json",
            new=AsyncMock(return_value=payload),
        ):
            result = await run_conflict_tagging(
                {"_id": "p1", "rationale_nodes": []},
                {"proposed_nodes": [position_a]},
                {"proposed_nodes": [position_b]},
                [position_a, position_b],
            )

        self.assertEqual(result["decision_issues"], payload["decision_issues"])
        self.assertEqual(result["position_tag_map"], {"node_pos_a": ["A"], "node_pos_b": ["A"]})

    async def test_conflict_tagging_ignores_refinement_relation(self) -> None:
        diagnosis = {
            "node_id": "node_pos_brand_copy_tone",
            "node_type": "position",
            "source_type": "brand_brief",
            "title": "旁白需要更内敛",
            "content": "脚本旁白风格过于口语化、生活化，需要向更克制、留白、隽永的方向调整。",
        }
        refinement = {
            "node_id": "node_pos_expert_refine_voiceover",
            "node_type": "position",
            "source_type": "expert_strategy",
            "title": "保留生活流并提纯旁白",
            "content": "不改变脚本生活流结构和真实细节，但将过于随意的口语转化为更具内省感和画面感的描述。",
        }
        payload = {
            "conflict_groups": [
                {
                    "tag": "A",
                    "relation_type": "refinement",
                    "reason": "专家方案回应并细化品牌侧诊断，不构成取舍冲突",
                    "position_ids": [
                        "node_pos_brand_copy_tone",
                        "node_pos_expert_refine_voiceover",
                    ],
                }
            ],
            "decision_issues": [],
        }

        with patch(
            "app.services.agents.coordinator_agent.invoke_agent_json",
            new=AsyncMock(return_value=payload),
        ):
            result = await run_conflict_tagging(
                {"_id": "p1", "rationale_nodes": []},
                {"proposed_nodes": [diagnosis]},
                None,
                [diagnosis, refinement],
            )

        self.assertEqual(result["position_tag_map"], {})
        self.assertEqual(result["existing_node_updates"], [])


class GraphSyncStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_stream_graph_sync_emits_status_heartbeat_and_done(self) -> None:
        async def slow_sync(*_args, **_kwargs):
            import asyncio

            await asyncio.sleep(0.02)
            return {"project": {"_id": "p1"}, "nodes_added": 0}

        with (
            patch("app.services.coordinator_service.sync_graph_from_script", new=slow_sync),
            patch("app.services.coordinator_service.GRAPH_SYNC_HEARTBEAT_SECONDS", 0.001),
        ):
            frames = []
            async for frame in stream_graph_sync(object(), "p1", "u1", changed_row_ids=[]):
                frames.append(frame)

        self.assertTrue(any("event: status" in frame for frame in frames))
        self.assertTrue(any("event: heartbeat" in frame for frame in frames))
        self.assertTrue(any("event: done" in frame for frame in frames))


if __name__ == "__main__":
    unittest.main()
