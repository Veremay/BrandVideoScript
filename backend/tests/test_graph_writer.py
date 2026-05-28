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

    def test_persist_ignores_edges_for_issue_only_batch(self) -> None:
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "issue",
                        "title": "Issue A",
                        "content": "…",
                        "source_type": "brand_brief",
                    }
                ],
                "edges": [{"from_index": 0, "to_index": 0, "relation_type": "responds_to"}],
            },
            allowed_source_types={"brand_brief", "brand_inferred"},
        )
        self.assertEqual(len(graph.proposed_edges), 0)

    def test_persist_skips_invalid_issue_to_issue_edges(self) -> None:
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "issue",
                        "title": "Issue A",
                        "content": "…",
                        "source_type": "brand_brief",
                    },
                    {
                        "node_type": "issue",
                        "title": "Issue B",
                        "content": "…",
                        "source_type": "brand_brief",
                    },
                ],
                "edges": [
                    {"from_index": 0, "to_index": 1, "relation_type": "responds_to"},
                ],
            },
            allowed_source_types={"brand_brief", "brand_inferred"},
        )
        self.assertEqual(len(graph.proposed_nodes), 2)
        self.assertEqual(len(graph.proposed_edges), 0)

    def test_persist_issue_only_batch(self) -> None:
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "issue",
                        "title": "待讨论",
                        "content": "尚无立场",
                        "source_type": "brand_brief",
                        "source_perspective": "brand",
                    }
                ],
            },
        )
        self.assertEqual(len(graph.proposed_nodes), 1)
        self.assertEqual(len(graph.proposed_edges), 0)

    def test_persist_auto_links_orphan_position_to_parent_issue(self) -> None:
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "生活化场景",
                        "content": "自然植入",
                        "source_type": "expert_strategy",
                        "layout": {"x": 240.0, "y": 80.0},
                    },
                    {
                        "node_type": "argument",
                        "title": "观众更易接受",
                        "content": "数据支撑",
                        "source_type": "expert_strategy",
                        "stance": "pro",
                        "layout": {"x": 320.0, "y": 80.0},
                    },
                ],
            },
            parent_issue_ids=["node_issue_brand_1", "node_issue_brand_2"],
        )
        self.assertEqual(len(graph.proposed_nodes), 2)
        self.assertGreaterEqual(len(graph.proposed_edges), 2)
        relations = {edge["relation_type"] for edge in graph.proposed_edges}
        self.assertIn("responds_to", relations)
        self.assertIn("supports", relations)

    def test_persist_rejects_orphan_position_without_parent_issue(self) -> None:
        with self.assertRaises(ValueError):
            persist_rationale_graph(
                "project_1",
                {
                    "nodes": [
                        {
                            "node_type": "position",
                            "title": "孤立立场",
                            "content": "未连 issue",
                            "source_type": "expert_strategy",
                        }
                    ],
                },
            )

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
