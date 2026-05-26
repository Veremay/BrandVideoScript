import unittest

from app.services.agent_context import assert_context_isolation, build_agent_context


class AgentContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = {
            "_id": "project_test",
            "platform_context": "xiaohongshu",
            "brief": {"text": "必须展示真实通勤场景", "summary": "通勤场景"},
            "brand_insights": [{"insight_id": "insight_1"}],
            "brand_perspective_result": {"explicit_requirements": []},
            "personas": [{"persona_id": "persona_1", "name": "测试观众"}],
            "active_persona_id": "persona_1",
            "audience_perspective_result": {"naturalness": "ok"},
            "rationale_nodes": [{"node_id": "node_1", "source_type": "brand_brief"}],
            "current_script": {"columns": [], "rows": []},
        }

    def test_brand_context_excludes_persona_and_audience(self) -> None:
        context = build_agent_context("brand", self.project)
        assert_context_isolation("brand", context)
        self.assertIn("brief", context)
        self.assertNotIn("personas", context)
        self.assertNotIn("audience_perspective_result", context)

    def test_audience_context_excludes_brief_and_brand(self) -> None:
        context = build_agent_context("audience", self.project)
        assert_context_isolation("audience", context)
        self.assertIn("active_persona", context)
        self.assertNotIn("brief", context)
        self.assertNotIn("brand_perspective_result", context)

    def test_expert_context_includes_structured_results_not_chat(self) -> None:
        context = build_agent_context("expert", self.project)
        assert_context_isolation("expert", context)
        self.assertIn("brand_perspective_result", context)
        self.assertIn("audience_perspective_result", context)
        self.assertEqual(context["brief_summary"], "通勤场景")


if __name__ == "__main__":
    unittest.main()
