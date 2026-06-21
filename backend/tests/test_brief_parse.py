import unittest

from app.services.agents.brand_agent import run_brand_agent
from app.services.agents.expert_agent import run_expert_for_brief, run_expert_populate_issue
from app.services.agent_context import build_agent_context


class BriefParseAgentsTest(unittest.IsolatedAsyncioTestCase):
    async def test_brand_agent_produces_brand_sourced_positions(self) -> None:
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

        # Bottom-up model: Brand emits Positions (stances), never standalone Issues.
        brand_node_types = {node.get("node_type") for node in brand.get("proposed_nodes", [])}
        self.assertIn("position", brand_node_types)
        self.assertNotIn("issue", brand_node_types)
        brand_position_sources = {
            node.get("source_type")
            for node in brand.get("proposed_nodes", [])
            if node.get("node_type") == "position"
        }
        self.assertTrue(brand_position_sources.intersection({"brand_brief", "brand_inferred"}))
        self.assertGreaterEqual(len(brand.get("explicit_requirements", [])), 1)

        # Expert derives a conflict Issue from the brand position + an expert counter-position.
        expert_node_types = {node.get("node_type") for node in expert.get("proposed_nodes", [])}
        self.assertIn("issue", expert_node_types)
        relations = {edge.get("relation_type") for edge in expert.get("proposed_edges", [])}
        self.assertIn("responds_to", relations)
        self.assertIn("conflicts_with", relations)

    async def test_populate_issue_organizes_conflicting_positions(self) -> None:
        issue_id = "node_issue_user_1"
        project = {
            "_id": "project_pop",
            "platform_context": "xiaohongshu",
            "current_script_version_id": "ver_1",
            "current_script": {"columns": [], "rows": []},
            "rationale_nodes": [
                {
                    "node_id": issue_id,
                    "node_type": "issue",
                    "title": "品牌露出强度",
                    "content": "用户提出的议题",
                    "source_type": "creator_manual",
                    "created_by": "user",
                }
            ],
            "rationale_edges": [],
        }
        issue = project["rationale_nodes"][0]
        result = await run_expert_populate_issue(project, issue)

        positions = [n for n in result["proposed_nodes"] if n.get("node_type") == "position"]
        self.assertGreaterEqual(len(positions), 2)
        responds = [e for e in result["proposed_edges"] if e["relation_type"] == "responds_to"]
        conflicts = [e for e in result["proposed_edges"] if e["relation_type"] == "conflicts_with"]
        self.assertGreaterEqual(len(responds), 2)
        self.assertTrue(all(e["to_node_id"] == issue_id for e in responds))
        self.assertGreaterEqual(len(conflicts), 1)

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
