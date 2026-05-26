import unittest

from app.models.rationale_ops import build_rationale_node, merge_proposed_graph


class GraphMergeTest(unittest.TestCase):
    def test_merge_does_not_replace_user_nodes(self) -> None:
        user_node = build_rationale_node(
            project_id="p1",
            node_type="issue",
            title="User issue",
            content="Keep me",
            source_type="creator_manual",
            created_by="user",
        )
        agent_node = build_rationale_node(
            project_id="p1",
            node_type="issue",
            title="Agent issue",
            content="New",
            source_type="brand_brief",
            created_by="agent",
        )
        safe = [n for n in [agent_node] if n["node_id"] not in {user_node["node_id"]}]
        nodes, edges = merge_proposed_graph(
            project_id="p1",
            existing_nodes=[user_node],
            existing_edges=[],
            proposed_nodes=safe,
            proposed_edges=[],
        )
        titles = {node["title"] for node in nodes}
        self.assertIn("User issue", titles)
        self.assertIn("Agent issue", titles)


if __name__ == "__main__":
    unittest.main()
