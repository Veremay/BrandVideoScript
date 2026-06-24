import unittest

from app.services.agents.brand_agent import run_brand_agent
from app.services.agents.expert_agent import run_expert_for_conflicts
from app.services.agent_context import build_agent_context
from app.services.agent_orchestrator import run_issue_population_pipeline


class BriefParseAgentsTest(unittest.IsolatedAsyncioTestCase):
    async def test_brand_agent_produces_brand_sourced_positions(self) -> None:
        project = {
            "_id": "project_parse",
            "platform_context": "xiaohongshu",
            "brief": {
                "text": "必须展示真实通勤\n避免硬广口播",
                "summary": "通勤与口播约束",
            },
            "brand_insights": [{
                "insight_id": "insight_test_1",
                "agent_type": "brand",
                "category": "explicit_requirement",
                "title": "通勤展示",
                "content": "必须展示真实通勤",
                "reason": "Brief 明确要求",
                "evidence": [],
                "confidence": "high",
                "status": "new",
                "created_by": "agent",
                "updated_by": "agent",
                "based_on_script_version_id": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }],
            "brand_perspective_result": {
                "constraints": [],
                "pr_risks": [],
            },
            "personas": [{"persona_id": "persona_1", "name": "A", "trust_trigger": [], "reject_trigger": []}],
            "active_persona_id": "persona_1",
            "current_script_version_id": "script_ver_1",
            "current_script": {"columns": [], "rows": []},
            "rationale_nodes": [],
            "rationale_edges": [],
        }
        brand = await run_brand_agent(project, task_context="coordinator")
        from app.services.agents.audience_agent import run_audience_agent

        audience = await run_audience_agent(project)
        expert = await run_expert_for_conflicts(project, brand, audience)

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

        # Expert derives conflict issues from brand + audience positions.
        expert_node_types = {node.get("node_type") for node in expert.get("proposed_nodes", [])}
        self.assertIn("issue", expert_node_types)
        relations = {edge.get("relation_type") for edge in expert.get("proposed_edges", [])}
        self.assertIn("responds_to", relations)

    async def test_populate_issue_generates_brand_and_audience_positions(self) -> None:
        issue_id = "node_issue_user_1"
        project = {
            "_id": "project_pop",
            "platform_context": "xiaohongshu",
            "brand_insights": [{
                "insight_id": "insight_test_2",
                "agent_type": "brand",
                "category": "explicit_requirement",
                "title": "品牌露出",
                "content": "品牌露出",
                "reason": "Brief 要求",
                "evidence": [],
                "confidence": "high",
                "status": "new",
                "created_by": "agent",
                "updated_by": "agent",
                "based_on_script_version_id": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }],
            "brand_perspective_result": {
                "constraints": [],
                "pr_risks": [],
            },
            "personas": [{"persona_id": "persona_1", "name": "A", "trust_trigger": [], "reject_trigger": []}],
            "active_persona_id": "persona_1",
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
        pipeline = await run_issue_population_pipeline(project, issue_id)

        positions = [n for n in pipeline.proposed_nodes if n.get("node_type") == "position"]
        self.assertGreaterEqual(len(positions), 2)
        responds = [e for e in pipeline.proposed_edges if e["relation_type"] == "responds_to"]
        self.assertGreaterEqual(len(responds), 2)
        self.assertTrue(all(e["to_node_id"] == issue_id for e in responds))
        sources = {p.get("source_type") for p in positions}
        self.assertTrue(sources.intersection({"brand_brief", "brand_inferred"}))
        self.assertTrue(sources.intersection({"audience_persona", "audience_simulation"}))

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
