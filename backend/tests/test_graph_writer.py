import unittest

from app.services.agent_context import build_agent_context
from app.services.prompt_loader import load_prompt
from app.services.tools.ibis_graph import persist_rationale_graph


class IbisGraphToolTest(unittest.TestCase):
    def test_ibis_types_in_agent_prompts(self) -> None:
        for name in ("brand_agent.md", "audience_agent.md", "expert_agent.md"):
            prompt = load_prompt(name)
            self.assertIn("persist_rationale_graph", prompt)

    def test_persist_tool_materializes_nodes_and_external_edges(self) -> None:
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "立场",
                        "content": "内容",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    }
                ],
                "external_edges": [
                    {"from_index": 0, "to_node_id": "node_issue_1", "relation_type": "responds_to"}
                ],
            },
            script_version_id="ver_1",
        )
        self.assertEqual(len(graph.proposed_nodes), 1)
        self.assertEqual(len(graph.proposed_edges), 1)
        self.assertEqual(graph.proposed_edges[0]["to_node_id"], "node_issue_1")

    def test_audience_context_isolation(self) -> None:
        context = build_agent_context(
            "audience",
            {
                "_id": "p1",
                "brief": {"text": "SECRET BRIEF"},
                "personas": [{"persona_id": "per_1", "name": "A", "trust_trigger": [], "reject_trigger": []}],
                "active_persona_id": "per_1",
                "current_script": {"columns": [], "rows": []},
            },
        )
        self.assertNotIn("brief", context)


if __name__ == "__main__":
    unittest.main()
