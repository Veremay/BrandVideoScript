import unittest

from app.models.rationale_ops import (
    build_rationale_node,
    merge_proposed_graph,
    validate_ibis_edge,
    validate_ibis_graph_integrity,
)


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


class IbisEdgeValidationTest(unittest.TestCase):
    def test_validate_allowed_links(self) -> None:
        issue = {"node_type": "issue"}
        position = {"node_type": "position"}
        argument = {"node_type": "argument"}
        validate_ibis_edge(position, issue, "responds_to")
        validate_ibis_edge(argument, position, "supports")

    def test_validate_rejects_invalid_links(self) -> None:
        issue = {"node_type": "issue"}
        position = {"node_type": "position"}
        argument = {"node_type": "argument"}
        with self.assertRaises(ValueError):
            validate_ibis_edge(position, position, "responds_to")
        with self.assertRaises(ValueError):
            validate_ibis_edge(issue, argument, "responds_to")


class IbisGraphIntegrityTest(unittest.TestCase):
    def test_issue_without_position_is_valid(self) -> None:
        issue = build_rationale_node(
            project_id="p1",
            node_type="issue",
            title="Open question",
            content="No answers yet",
            source_type="brand_brief",
            created_by="agent",
        )
        validate_ibis_graph_integrity([issue], [], require_linked_for=lambda _node: True)

    def test_orphan_position_fails_integrity(self) -> None:
        position = build_rationale_node(
            project_id="p1",
            node_type="position",
            title="Orphan stance",
            content="Unlinked",
            source_type="expert_strategy",
            created_by="agent",
        )
        with self.assertRaises(ValueError):
            validate_ibis_graph_integrity([position], [], require_linked_for=lambda _node: True)

    def test_user_orphan_position_allowed_by_default(self) -> None:
        position = build_rationale_node(
            project_id="p1",
            node_type="position",
            title="Draft stance",
            content="Connect on canvas",
            source_type="creator_manual",
            created_by="user",
        )
        validate_ibis_graph_integrity([position], [])

    def test_merge_allows_user_orphan_position(self) -> None:
        user_position = build_rationale_node(
            project_id="p1",
            node_type="position",
            title="User draft",
            content="WIP",
            source_type="creator_manual",
            created_by="user",
        )
        agent_issue = build_rationale_node(
            project_id="p1",
            node_type="issue",
            title="New issue",
            content="From agent",
            source_type="brand_brief",
            created_by="agent",
        )
        nodes, edges = merge_proposed_graph(
            project_id="p1",
            existing_nodes=[user_position],
            existing_edges=[],
            proposed_nodes=[agent_issue],
            proposed_edges=[],
        )
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(edges), 0)


if __name__ == "__main__":
    unittest.main()
