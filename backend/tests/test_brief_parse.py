import unittest

from app.services.agents.brand_agent import run_brand_agent
from app.services.agents.expert_agent import run_expert_for_brief
from app.services.agent_context import build_agent_context


class BriefParseAgentsTest(unittest.IsolatedAsyncioTestCase):
    async def test_brand_agent_produces_brand_sourced_issues(self) -> None:
        project = {
            "_id": "project_parse",
            "platform_context": "xiaohongshu",
            "brief": {
                "text": "必须展示真实通勤\n避免硬广口播",
                "summary": "通勤与口播约束",
            },
            "brand_insights": [],
            "personas": [],
            "active_persona_id": None,
            "current_script_version_id": "script_ver_1",
            "current_script": {"columns": [], "rows": []},
            "rationale_nodes": [],
            "rationale_edges": [],
        }
        brand = await run_brand_agent(project)
        expert = await run_expert_for_brief(project, brand)

        issue_sources = {
            node.get("source_type")
            for node in expert.get("proposed_nodes", [])
            if node.get("node_type") == "issue"
        }
        self.assertTrue(issue_sources.intersection({"brand_brief", "brand_inferred"}))
        self.assertGreaterEqual(len(brand.get("explicit_requirements", [])), 1)
        self.assertGreaterEqual(len(expert.get("proposed_edges", [])), 1)

    def test_audience_context_cannot_see_brief(self) -> None:
        project = {
            "_id": "p1",
            "brief": {"text": "secret brief"},
            "personas": [{"persona_id": "persona_1", "name": "A", "trust_trigger": [], "reject_trigger": []}],
            "active_persona_id": "persona_1",
            "current_script": {"columns": [], "rows": []},
        }
        context = build_agent_context("audience", project)
        self.assertNotIn("brief", context)


if __name__ == "__main__":
    unittest.main()
