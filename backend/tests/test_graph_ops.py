import unittest
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from app.models.rationale_ops import (
    apply_reconcile,
    build_rationale_edge,
    build_rationale_node,
    collect_issue_delete_cascade,
    drop_agent_issues_without_positions,
    merge_proposed_graph,
    resolve_issue,
    supersede_node,
    validate_ibis_edge,
    validate_ibis_graph_integrity,
)
from app.models.schemas import GraphNodeCreateRequest


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
        user_issue = build_rationale_node(
            project_id="p1",
            node_type="issue",
            title="User issue",
            content="Keep user position",
            source_type="creator_manual",
            created_by="user",
        )
        agent_issue = build_rationale_node(
            project_id="p1",
            node_type="issue",
            title="Agent issue",
            content="Agent position carrier",
            source_type="brand_brief",
            created_by="agent",
        )
        agent_argument = build_rationale_node(
            project_id="p1",
            node_type="argument",
            title="Agent argument",
            content="Supports agent position",
            source_type="brand_brief",
            created_by="agent",
        )
        existing_edges = [_edge(user_node, user_issue, "responds_to")]
        proposed_edges = [
            _edge(agent_node, agent_issue, "responds_to"),
            _edge(agent_argument, agent_node, "supports"),
        ]
        nodes, _edges = merge_proposed_graph(
            project_id="p1",
            existing_nodes=[user_node, user_issue],
            existing_edges=existing_edges,
            proposed_nodes=[agent_node, agent_issue, agent_argument],
            proposed_edges=proposed_edges,
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


class GraphNodeSchemaTest(unittest.TestCase):
    def test_create_request_rejects_blank_title(self) -> None:
        with self.assertRaises(ValidationError):
            GraphNodeCreateRequest(
                user_id="u1",
                node_type="issue",
                title="   ",
                content="content",
            )

    def test_create_request_rejects_unknown_source_perspective(self) -> None:
        with self.assertRaises(ValidationError):
            GraphNodeCreateRequest(
                user_id="u1",
                node_type="issue",
                title="Issue",
                content="content",
                source_perspective="unknown",
            )


class IbisGraphIntegrityTest(unittest.TestCase):
    def test_orphan_position_fails(self) -> None:
        position = _node("position")
        with self.assertRaises(ValueError):
            validate_ibis_graph_integrity([position], [], require_linked_for=lambda _node: True)

    def test_issue_without_positions_fails(self) -> None:
        issue = _node("issue")
        with self.assertRaises(ValueError):
            validate_ibis_graph_integrity([issue], [], require_linked_for=lambda _node: True)

    def test_issue_with_one_position_is_valid(self) -> None:
        position = _node("position")
        issue = _node("issue")
        argument = _node("argument")
        edges = [_edge(position, issue, "responds_to"), _edge(argument, position, "supports")]
        validate_ibis_graph_integrity(
            [position, issue, argument], edges, require_linked_for=lambda _node: True
        )

    def test_position_without_argument_fails(self) -> None:
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
        arg_a = _node("argument")
        arg_b = _node("argument")
        edges = [
            _edge(pos_a, issue, "responds_to"),
            _edge(pos_b, issue, "responds_to"),
            _edge(pos_a, pos_b, "conflicts_with"),
            _edge(arg_a, pos_a, "supports"),
            _edge(arg_b, pos_b, "supports"),
        ]
        validate_ibis_graph_integrity(
            [pos_a, pos_b, issue, arg_a, arg_b], edges, require_linked_for=lambda _node: True
        )

    def test_argument_without_position_fails(self) -> None:
        argument = _node("argument")
        with self.assertRaises(ValueError):
            validate_ibis_graph_integrity([argument], [], require_linked_for=lambda _node: True)

    def test_user_issue_not_force_checked_by_default(self) -> None:
        issue = _node("issue", created_by="user", source_type="creator_manual")
        validate_ibis_graph_integrity([issue], [])


class DropOrphanAgentIssuesTest(unittest.TestCase):
    def test_drops_agent_issue_when_last_position_removed(self) -> None:
        pos_a = _node("position")
        pos_b = _node("position")
        issue = _node("issue")
        edges = [
            _edge(pos_a, issue, "responds_to"),
            _edge(pos_b, issue, "responds_to"),
            _edge(pos_a, pos_b, "conflicts_with"),
        ]
        nodes = [pos_a, pos_b, issue]
        nodes_after = [pos_b, issue]
        edges_after = [_edge(pos_b, issue, "responds_to")]

        pruned_nodes, pruned_edges, dropped = drop_agent_issues_without_positions(
            nodes_after, edges_after, {issue["node_id"]}
        )
        self.assertEqual(dropped, set())
        self.assertEqual(len(pruned_nodes), 2)

        pruned_nodes, pruned_edges, dropped = drop_agent_issues_without_positions(
            [issue], [], {issue["node_id"]}
        )
        self.assertEqual(dropped, {issue["node_id"]})
        self.assertEqual(pruned_nodes, [])
        self.assertEqual(pruned_edges, [])

    def test_keeps_user_issue_when_last_position_removed(self) -> None:
        issue = _node("issue", created_by="user", source_type="creator_manual")
        nodes, edges, dropped = drop_agent_issues_without_positions([issue], [], {issue["node_id"]})
        self.assertEqual(dropped, set())
        self.assertEqual(nodes, [issue])

    def test_keeps_resolved_issue_without_positions(self) -> None:
        issue = _node("issue")
        issue["lifecycle"] = "resolved"
        nodes, edges, dropped = drop_agent_issues_without_positions([issue], [], {issue["node_id"]})
        self.assertEqual(dropped, set())
        self.assertEqual(nodes, [issue])


class IssueDeleteCascadeTest(unittest.TestCase):
    def test_issue_delete_includes_positions_and_arguments(self) -> None:
        pos_a = _node("position")
        pos_b = _node("position")
        issue = _node("issue")
        arg = _node("argument")
        edges = [
            _edge(pos_a, issue, "responds_to"),
            _edge(pos_b, issue, "responds_to"),
            _edge(pos_a, pos_b, "conflicts_with"),
            _edge(arg, pos_a, "supports"),
        ]
        nodes_by_id = {n["node_id"]: n for n in [pos_a, pos_b, issue, arg]}
        cascade = collect_issue_delete_cascade(nodes_by_id, edges, issue["node_id"])
        self.assertEqual(cascade, {issue["node_id"], pos_a["node_id"], pos_b["node_id"], arg["node_id"]})

    def test_position_delete_includes_arguments(self) -> None:
        pos = _node("position")
        arg = _node("argument")
        edge = _edge(arg, pos, "supports")
        nodes_by_id = {n["node_id"]: n for n in [pos, arg]}
        from app.models.rationale_ops import collect_position_delete_cascade

        self.assertEqual(collect_position_delete_cascade(nodes_by_id, [edge], pos["node_id"]), {pos["node_id"], arg["node_id"]})

    def test_argument_delete_does_not_cascade_position(self) -> None:
        pos = _node("position")
        arg = _node("argument")
        edge = _edge(arg, pos, "supports")
        nodes_by_id = {n["node_id"]: n for n in [pos, arg]}
        from app.models.rationale_ops import collect_argument_delete_cascade

        self.assertEqual(collect_argument_delete_cascade(nodes_by_id, [edge], arg["node_id"]), {arg["node_id"]})


class MergeValidationTest(unittest.TestCase):
    def test_merge_drops_agent_orphan_issue(self) -> None:
        """Orphan agent Issues are pruned during merge instead of failing the pipeline."""
        user_position = build_rationale_node(
            project_id="p1",
            node_type="position",
            title="User draft",
            content="WIP",
            source_type="creator_manual",
            created_by="user",
        )
        agent_issue = _node("issue")
        nodes, edges = merge_proposed_graph(
            project_id="p1",
            existing_nodes=[user_position],
            existing_edges=[],
            proposed_nodes=[agent_issue],
            proposed_edges=[],
        )
        self.assertEqual(nodes, [user_position])
        self.assertEqual(edges, [])

    def test_merge_rejects_orphan_position(self) -> None:
        position = _node("position", source_type="brand_brief")
        with self.assertRaises(ValueError):
            merge_proposed_graph(
                project_id="p1",
                existing_nodes=[],
                existing_edges=[],
                proposed_nodes=[position],
                proposed_edges=[],
            )

    def test_merge_keeps_conflict_issue(self) -> None:
        pos_a = _node("position", source_type="brand_brief")
        pos_b = _node("position", source_type="audience_simulation")
        issue = _node("issue")
        arg_a = _node("argument", source_type="brand_brief")
        arg_b = _node("argument", source_type="audience_simulation")
        proposed_edges = [
            _edge(pos_a, issue, "responds_to"),
            _edge(pos_b, issue, "responds_to"),
            _edge(pos_a, pos_b, "conflicts_with"),
            _edge(arg_a, pos_a, "supports"),
            _edge(arg_b, pos_b, "supports"),
        ]
        nodes, edges = merge_proposed_graph(
            project_id="p1",
            existing_nodes=[],
            existing_edges=[],
            proposed_nodes=[pos_a, pos_b, issue, arg_a, arg_b],
            proposed_edges=proposed_edges,
        )
        self.assertEqual(len(nodes), 5)
        self.assertEqual(len(edges), 5)


class ReconcileTest(unittest.TestCase):
    def _conflict_graph(self, *, created_by: str = "agent"):
        pos_a = _node("position", created_by=created_by, source_type="brand_brief")
        pos_b = _node("position", created_by=created_by, source_type="audience_simulation")
        issue = _node("issue", created_by=created_by)
        arg_a = _node("argument", created_by=created_by, source_type="brand_brief")
        arg_b = _node("argument", created_by=created_by, source_type="audience_simulation")
        edges = [
            _edge(pos_a, issue, "responds_to"),
            _edge(pos_b, issue, "responds_to"),
            _edge(pos_a, pos_b, "conflicts_with"),
            _edge(arg_a, pos_a, "supports"),
            _edge(arg_b, pos_b, "supports"),
        ]
        return pos_a, pos_b, issue, arg_a, arg_b, edges

    def test_still_holds_keeps_ids(self) -> None:
        pos_a, pos_b, issue, arg_a, arg_b, edges = self._conflict_graph()
        nodes, out_edges = apply_reconcile(
            project_id="p1",
            existing_nodes=[pos_a, pos_b, issue, arg_a, arg_b],
            existing_edges=edges,
            issue_reviews=[{"issue_id": issue["node_id"], "verdict": "still_holds"}],
        )
        by_id = {n["node_id"]: n for n in nodes}
        self.assertIn(issue["node_id"], by_id)
        self.assertEqual(by_id[issue["node_id"]]["lifecycle"], "active")
        self.assertEqual(len(out_edges), 5)

    def test_resolved_marks_issue_keeps_positions(self) -> None:
        pos_a, pos_b, issue, arg_a, arg_b, edges = self._conflict_graph()
        nodes, out_edges = apply_reconcile(
            project_id="p1",
            existing_nodes=[pos_a, pos_b, issue, arg_a, arg_b],
            existing_edges=edges,
            issue_reviews=[{"issue_id": issue["node_id"], "verdict": "resolved"}],
        )
        by_id = {n["node_id"]: n for n in nodes}
        self.assertEqual(by_id[issue["node_id"]]["lifecycle"], "resolved")
        self.assertIsNotNone(by_id[issue["node_id"]]["resolved_at"])
        # Positions stay active and present.
        self.assertEqual(by_id[pos_a["node_id"]]["lifecycle"], "active")
        self.assertEqual(by_id[pos_b["node_id"]]["lifecycle"], "active")

    def test_resolved_issue_revives_on_next_pass(self) -> None:
        pos_a, pos_b, issue, arg_a, arg_b, edges = self._conflict_graph()
        issue["lifecycle"] = "resolved"
        issue["resolved_at"] = "2020-01-01T00:00:00Z"
        nodes, _ = apply_reconcile(
            project_id="p1",
            existing_nodes=[pos_a, pos_b, issue, arg_a, arg_b],
            existing_edges=edges,
            issue_reviews=[{"issue_id": issue["node_id"], "verdict": "still_holds"}],
        )
        by_id = {n["node_id"]: n for n in nodes}
        self.assertEqual(by_id[issue["node_id"]]["lifecycle"], "active")
        self.assertIsNone(by_id[issue["node_id"]]["resolved_at"])

    def test_modified_issue_supersedes_with_new_id_inheriting_edges(self) -> None:
        pos_a, pos_b, issue, arg_a, arg_b, edges = self._conflict_graph()
        nodes, out_edges = apply_reconcile(
            project_id="p1",
            existing_nodes=[pos_a, pos_b, issue, arg_a, arg_b],
            existing_edges=edges,
            issue_reviews=[
                {
                    "issue_id": issue["node_id"],
                    "verdict": "modified",
                    "new_title": "Reframed conflict",
                    "new_content": "Sharper focus",
                }
            ],
        )
        ids = {n["node_id"] for n in nodes}
        self.assertNotIn(issue["node_id"], ids)  # old issue dropped from live graph
        new_issue = next(n for n in nodes if n["node_type"] == "issue")
        self.assertEqual(new_issue["change_mark"], "modified")
        self.assertEqual(new_issue["predecessor_id"], issue["node_id"])
        self.assertEqual(new_issue["title"], "Reframed conflict")
        # The new issue still aggregates the two positions (inherited responds_to).
        responds = [
            e for e in out_edges
            if e["relation_type"] == "responds_to" and e["to_node_id"] == new_issue["node_id"]
        ]
        self.assertEqual(len(responds), 2)

    def test_user_node_only_gets_suggestion(self) -> None:
        pos_a, pos_b, issue, arg_a, arg_b, edges = self._conflict_graph(created_by="user")
        nodes, _ = apply_reconcile(
            project_id="p1",
            existing_nodes=[pos_a, pos_b, issue, arg_a, arg_b],
            existing_edges=edges,
            issue_reviews=[{"issue_id": issue["node_id"], "verdict": "resolved"}],
        )
        by_id = {n["node_id"]: n for n in nodes}
        self.assertEqual(by_id[issue["node_id"]]["lifecycle"], "active")  # untouched
        self.assertEqual(by_id[issue["node_id"]]["suggestion"], "resolved?")

    def test_new_conflict_marked_new(self) -> None:
        pos_a, pos_b, issue, arg_a, arg_b, edges = self._conflict_graph()
        new_pos_a = _node("position", source_type="brand_brief")
        new_pos_b = _node("position", source_type="expert_strategy")
        new_issue = _node("issue")
        new_arg_a = _node("argument", source_type="brand_brief")
        new_arg_b = _node("argument", source_type="expert_strategy")
        nodes, _ = apply_reconcile(
            project_id="p1",
            existing_nodes=[pos_a, pos_b, issue, arg_a, arg_b],
            existing_edges=edges,
            issue_reviews=[{"issue_id": issue["node_id"], "verdict": "still_holds"}],
            new_nodes=[new_pos_a, new_pos_b, new_issue, new_arg_a, new_arg_b],
            new_edges=[
                _edge(new_pos_a, new_issue, "responds_to"),
                _edge(new_pos_b, new_issue, "responds_to"),
                _edge(new_pos_a, new_pos_b, "conflicts_with"),
                _edge(new_arg_a, new_pos_a, "supports"),
                _edge(new_arg_b, new_pos_b, "supports"),
            ],
        )
        by_id = {n["node_id"]: n for n in nodes}
        self.assertEqual(by_id[new_issue["node_id"]]["change_mark"], "new")
        self.assertEqual(by_id[issue["node_id"]]["change_mark"], "none")


class ReconcilePipelineWiringTest(unittest.TestCase):
    def test_reconcile_pipeline_applies_reviews(self) -> None:
        from app.services.agent_orchestrator import (
            AgentPipelineResult,
            reconcile_pipeline_into_project_graph,
        )

        pos_a = _node("position", source_type="brand_brief")
        pos_b = _node("position", source_type="audience_simulation")
        issue = _node("issue")
        arg_a = _node("argument", source_type="brand_brief")
        arg_b = _node("argument", source_type="audience_simulation")
        edges = [
            _edge(pos_a, issue, "responds_to"),
            _edge(pos_b, issue, "responds_to"),
            _edge(pos_a, pos_b, "conflicts_with"),
            _edge(arg_a, pos_a, "supports"),
            _edge(arg_b, pos_b, "supports"),
        ]
        project = {
            "_id": "p1",
            "rationale_nodes": [pos_a, pos_b, issue, arg_a, arg_b],
            "rationale_edges": edges,
        }
        pipeline = AgentPipelineResult()
        pipeline.issue_reviews = [{"issue_id": issue["node_id"], "verdict": "resolved"}]

        nodes, _edges = reconcile_pipeline_into_project_graph(project, pipeline)
        by_id = {n["node_id"]: n for n in nodes}
        self.assertEqual(by_id[issue["node_id"]]["lifecycle"], "resolved")


class MapUpdateDecisionIssueTest(unittest.IsolatedAsyncioTestCase):
    async def test_coordinator_decision_issue_creates_issue_and_responds_edges(self) -> None:
        from app.services.agent_orchestrator import run_map_update_pipeline

        brand_position = _node("position", source_type="brand_brief")
        brand_position["title"] = "品牌前三秒露出产品"
        audience_position = _node("position", source_type="audience_simulation")
        audience_position["title"] = "观众需要自然开场"
        argument = _node("argument", source_type="audience_simulation")
        argument_edge = _edge(argument, audience_position, "supports")
        project = {
            "_id": "p1",
            "active_persona_id": None,
            "rationale_nodes": [],
            "rationale_edges": [],
        }

        with (
            patch(
                "app.services.agent_orchestrator.run_brand_agent",
                new=AsyncMock(return_value={"proposed_nodes": [brand_position], "proposed_edges": []}),
            ),
            patch(
                "app.services.agent_orchestrator.run_expert_for_map_update",
                new=AsyncMock(return_value={"proposed_nodes": [audience_position, argument], "proposed_edges": [argument_edge]}),
            ),
            patch(
                "app.services.agent_orchestrator.run_conflict_tagging",
                new=AsyncMock(
                    return_value={
                        "position_tag_map": {
                            brand_position["node_id"]: ["A"],
                            audience_position["node_id"]: ["A"],
                        },
                        "existing_node_updates": [],
                        "decision_issues": [
                            {
                                "title": "品牌露出时机如何兼顾信息传达与自然感？",
                                "content": "多个立场都在回应产品露出时机与自然开场之间的取舍。",
                                "position_ids": [
                                    brand_position["node_id"],
                                    audience_position["node_id"],
                                ],
                            }
                        ],
                    }
                ),
            ),
        ):
            pipeline = await run_map_update_pipeline(project)

        issues = [node for node in pipeline.proposed_nodes if node["node_type"] == "issue"]
        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual(issue["title"], "品牌露出时机如何兼顾信息传达与自然感？")
        responds = [
            edge
            for edge in pipeline.proposed_edges
            if edge["relation_type"] == "responds_to" and edge["to_node_id"] == issue["node_id"]
        ]
        self.assertEqual({edge["from_node_id"] for edge in responds}, {brand_position["node_id"], audience_position["node_id"]})
        self.assertIn(argument_edge, pipeline.proposed_edges)

    async def test_conflict_tags_without_decision_issue_do_not_create_issue(self) -> None:
        from app.services.agent_orchestrator import run_map_update_pipeline

        brand_position = _node("position", source_type="brand_brief")
        audience_position = _node("position", source_type="audience_simulation")
        project = {
            "_id": "p1",
            "active_persona_id": None,
            "rationale_nodes": [],
            "rationale_edges": [],
        }

        with (
            patch(
                "app.services.agent_orchestrator.run_brand_agent",
                new=AsyncMock(return_value={"proposed_nodes": [brand_position], "proposed_edges": []}),
            ),
            patch(
                "app.services.agent_orchestrator.run_expert_for_map_update",
                new=AsyncMock(return_value={"proposed_nodes": [audience_position], "proposed_edges": []}),
            ),
            patch(
                "app.services.agent_orchestrator.run_conflict_tagging",
                new=AsyncMock(
                    return_value={
                        "position_tag_map": {
                            brand_position["node_id"]: ["A"],
                            audience_position["node_id"]: ["A"],
                        },
                        "existing_node_updates": [],
                        "conflict_groups": [
                            {
                                "tag": "A",
                                "reason": "单次冲突，尚未形成稳定决策轴",
                                "position_ids": [
                                    brand_position["node_id"],
                                    audience_position["node_id"],
                                ],
                            }
                        ],
                    }
                ),
            ),
        ):
            pipeline = await run_map_update_pipeline(project)

        issues = [node for node in pipeline.proposed_nodes if node["node_type"] == "issue"]
        self.assertEqual(len(issues), 2)
        responds = [edge for edge in pipeline.proposed_edges if edge["relation_type"] == "responds_to"]
        self.assertEqual({edge["from_node_id"] for edge in responds}, {brand_position["node_id"], audience_position["node_id"]})

    async def test_map_update_adds_carrier_issue_for_independent_position(self) -> None:
        from app.services.agent_orchestrator import run_map_update_pipeline

        brand_position = _node("position", source_type="brand_brief")
        brand_position["title"] = "品牌露出优先"
        project = {
            "_id": "p1",
            "active_persona_id": None,
            "rationale_nodes": [],
            "rationale_edges": [],
        }

        with (
            patch(
                "app.services.agent_orchestrator.run_brand_agent",
                new=AsyncMock(return_value={"proposed_nodes": [brand_position], "proposed_edges": []}),
            ),
            patch(
                "app.services.agent_orchestrator.run_expert_for_map_update",
                new=AsyncMock(return_value={"proposed_nodes": [], "proposed_edges": []}),
            ),
            patch(
                "app.services.agent_orchestrator.run_conflict_tagging",
                new=AsyncMock(return_value={"position_tag_map": {}, "existing_node_updates": [], "decision_issues": []}),
            ),
        ):
            pipeline = await run_map_update_pipeline(project)

        issues = [node for node in pipeline.proposed_nodes if node["node_type"] == "issue"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["title"], "关于「品牌露出优先」的议题")
        responds = [edge for edge in pipeline.proposed_edges if edge["relation_type"] == "responds_to"]
        self.assertEqual(len(responds), 1)
        self.assertEqual(responds[0]["from_node_id"], brand_position["node_id"])
        self.assertEqual(responds[0]["to_node_id"], issues[0]["node_id"])
        arguments = [node for node in pipeline.proposed_nodes if node["node_type"] == "argument"]
        self.assertEqual(len(arguments), 1)
        supports = [edge for edge in pipeline.proposed_edges if edge["relation_type"] == "supports"]
        self.assertEqual(len(supports), 1)
        self.assertEqual(supports[0]["from_node_id"], arguments[0]["node_id"])
        self.assertEqual(supports[0]["to_node_id"], brand_position["node_id"])


if __name__ == "__main__":
    unittest.main()
