import unittest

from app.models.rationale_ops import (
    build_rationale_edge,
    build_rationale_node,
    merge_proposed_graph,
    validate_ibis_edge,
    validate_ibis_graph_integrity,
)


def _node(node_type: str, *, created_by: str = "agent", source_type: str = "expert_strategy"):
    return build_rationale_node(
        project_id="p1",
        node_type=node_type,
        title=f"{node_type} node",
        content="…",
        source_type=source_type,
        created_by=created_by,
    )


def _edge(from_node, to_node, relation):
    return build_rationale_edge(
        project_id="p1",
        from_node_id=from_node["node_id"],
        to_node_id=to_node["node_id"],
        relation_type=relation,
    )


class GraphMergeTest(unittest.TestCase):
    def test_merge_does_not_replace_user_nodes(self) -> None:
        user_node = build_rationale_node(
            project_id="p1",
            node_type="position",
            title="User position",
            content="Keep me",
            source_type="creator_manual",
            created_by="user",
        )
        agent_node = build_rationale_node(
            project_id="p1",
            node_type="position",
            title="Agent position",
            content="New",
            source_type="brand_brief",
            created_by="agent",
        )
        nodes, _edges = merge_proposed_graph(
            project_id="p1",
            existing_nodes=[user_node],
            existing_edges=[],
            proposed_nodes=[agent_node],
            proposed_edges=[],
        )
        titles = {node["title"] for node in nodes}
        self.assertIn("User position", titles)
        self.assertIn("Agent position", titles)


class IbisEdgeValidationTest(unittest.TestCase):
    def test_validate_allowed_links(self) -> None:
        issue = {"node_type": "issue"}
        position = {"node_type": "position"}
        other_position = {"node_type": "position"}
        argument = {"node_type": "argument"}
        validate_ibis_edge(position, issue, "responds_to")
        validate_ibis_edge(argument, position, "supports")
        validate_ibis_edge(position, other_position, "conflicts_with")

    def test_validate_rejects_invalid_links(self) -> None:
        issue = {"node_type": "issue"}
        position = {"node_type": "position"}
        argument = {"node_type": "argument"}
        with self.assertRaises(ValueError):
            validate_ibis_edge(position, position, "responds_to")
        with self.assertRaises(ValueError):
            validate_ibis_edge(issue, argument, "responds_to")


class IbisGraphIntegrityTest(unittest.TestCase):
    def test_orphan_position_is_valid_root(self) -> None:
        position = _node("position")
        validate_ibis_graph_integrity([position], [], require_linked_for=lambda _node: True)

    def test_issue_without_two_positions_fails(self) -> None:
        position = _node("position")
        issue = _node("issue")
        edge = _edge(position, issue, "responds_to")
        with self.assertRaises(ValueError):
            validate_ibis_graph_integrity(
                [position, issue], [edge], require_linked_for=lambda _node: True
            )

    def test_issue_with_two_conflicting_positions_is_valid(self) -> None:
        pos_a = _node("position")
        pos_b = _node("position")
        issue = _node("issue")
        edges = [
            _edge(pos_a, issue, "responds_to"),
            _edge(pos_b, issue, "responds_to"),
            _edge(pos_a, pos_b, "conflicts_with"),
        ]
        validate_ibis_graph_integrity(
            [pos_a, pos_b, issue], edges, require_linked_for=lambda _node: True
        )

    def test_argument_without_position_fails(self) -> None:
        argument = _node("argument")
        with self.assertRaises(ValueError):
            validate_ibis_graph_integrity([argument], [], require_linked_for=lambda _node: True)

    def test_user_issue_not_force_checked_by_default(self) -> None:
        issue = _node("issue", created_by="user", source_type="creator_manual")
        validate_ibis_graph_integrity([issue], [])


class MergeValidationTest(unittest.TestCase):
    def test_merge_raises_on_agent_orphan_issue(self) -> None:
        """Orphan agent Issues surface as an error rather than being silently dropped."""
        user_position = build_rationale_node(
            project_id="p1",
            node_type="position",
            title="User draft",
            content="WIP",
            source_type="creator_manual",
            created_by="user",
        )
        agent_issue = _node("issue")
        with self.assertRaises(ValueError):
            merge_proposed_graph(
                project_id="p1",
                existing_nodes=[user_position],
                existing_edges=[],
                proposed_nodes=[agent_issue],
                proposed_edges=[],
            )

    def test_merge_keeps_conflict_issue(self) -> None:
        pos_a = _node("position", source_type="brand_brief")
        pos_b = _node("position", source_type="audience_simulation")
        issue = _node("issue")
        proposed_edges = [
            _edge(pos_a, issue, "responds_to"),
            _edge(pos_b, issue, "responds_to"),
            _edge(pos_a, pos_b, "conflicts_with"),
        ]
        nodes, edges = merge_proposed_graph(
            project_id="p1",
            existing_nodes=[],
            existing_edges=[],
            proposed_nodes=[pos_a, pos_b, issue],
            proposed_edges=proposed_edges,
        )
        self.assertEqual(len(nodes), 3)
        self.assertEqual(len(edges), 3)


if __name__ == "__main__":
    unittest.main()
