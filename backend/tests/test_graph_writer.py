import unittest

from app.services.agent_context import build_agent_context
from app.services.prompt_loader import load_prompt, render_prompt
from app.services.tools.ibis_graph import persist_rationale_graph


class IbisGraphToolTest(unittest.TestCase):
    def test_ibis_types_in_agent_prompts(self) -> None:
        ibis_types = load_prompt("ibis_types.md")
        expert_prompt = render_prompt(load_prompt("expert_agent.md"), {"IBIS_TYPES": ibis_types})
        self.assertIn("persist_rationale_graph", ibis_types)
        self.assertIn("persist_rationale_graph", expert_prompt)

    def test_persist_tool_materializes_position_with_issue_edge(self) -> None:
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "issue",
                        "title": "露出时机怎么安排？",
                        "content": "承载品牌露出立场",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    },
                    {
                        "node_type": "position",
                        "title": "立场",
                        "content": "内容",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    }
                ],
                "edges": [
                    {"from_index": 1, "to_index": 0, "relation_type": "responds_to"}
                ],
            },
            script_version_id="ver_1",
        )
        self.assertEqual(len(graph.proposed_nodes), 2)
        self.assertEqual(len(graph.proposed_edges), 1)
        self.assertEqual(graph.proposed_edges[0]["to_node_id"], graph.proposed_nodes[0]["node_id"])

    def test_persist_filters_nodes_missing_title(self) -> None:
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "issue",
                        "title": "",
                        "content": "No title",
                        "source_type": "expert_strategy",
                    },
                    {
                        "node_type": "position",
                        "content": "Missing title",
                        "source_type": "expert_strategy",
                    },
                ],
                "edges": [{"from_index": 1, "to_index": 0, "relation_type": "responds_to"}],
            },
        )
        self.assertEqual(graph.proposed_nodes, [])
        self.assertEqual(graph.proposed_edges, [])

    def test_persist_skips_self_referential_issue_edge(self) -> None:
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

    def test_persist_links_existing_positions_to_decision_issue(self) -> None:
        """Existing Positions can be wired into a new decision Issue via mixed-mode edges."""
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "issue",
                        "title": "立场冲突",
                        "content": "品牌 vs 观众",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    }
                ],
                "external_edges": [
                    {"from_node_id": "node_pos_brand", "to_index": 0, "relation_type": "responds_to"},
                    {"from_node_id": "node_pos_audience", "to_index": 0, "relation_type": "responds_to"},
                    {
                        "from_node_id": "node_pos_brand",
                        "to_node_id": "node_pos_audience",
                        "relation_type": "conflicts_with",
                    },
                ],
            },
            allowed_source_types={"expert_strategy"},
        )
        self.assertEqual(len(graph.proposed_nodes), 1)
        issue_id = graph.proposed_nodes[0]["node_id"]
        responds = [e for e in graph.proposed_edges if e["relation_type"] == "responds_to"]
        conflicts = [e for e in graph.proposed_edges if e["relation_type"] == "conflicts_with"]
        self.assertEqual(len(responds), 2)
        self.assertTrue(all(e["to_node_id"] == issue_id for e in responds))
        self.assertEqual(len(conflicts), 1)

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
        self.assertEqual(len(graph.proposed_nodes), 0)
        self.assertEqual(len(graph.proposed_edges), 0)

    def test_persist_filters_position_without_issue(self) -> None:
        """Positions must be carried by an Issue via responds_to."""
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "品牌露出优先",
                        "content": "品牌立场",
                        "source_type": "brand_brief",
                        "source_perspective": "brand",
                    }
                ],
            },
        )
        self.assertEqual(len(graph.proposed_nodes), 0)
        self.assertEqual(len(graph.proposed_edges), 0)

    def test_persist_auto_links_orphan_argument_to_position(self) -> None:
        graph = persist_rationale_graph(
            "project_1",
            {
                "nodes": [
                    {
                        "node_type": "issue",
                        "title": "生活化场景怎么承载卖点？",
                        "content": "承载策略立场",
                        "source_type": "expert_strategy",
                        "layout": {"x": 160.0, "y": 80.0},
                    },
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
                "edges": [{"from_index": 1, "to_index": 0, "relation_type": "responds_to"}],
            },
        )
        self.assertEqual(len(graph.proposed_nodes), 3)
        relations = {edge["relation_type"] for edge in graph.proposed_edges}
        self.assertIn("supports", relations)
        self.assertIn("responds_to", relations)

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
