from __future__ import annotations

from typing import Any

from app.models.script import new_id, now_iso

NODE_TYPES = {"issue", "position", "argument", "reference"}
SOURCE_TYPES = {
    "brand_brief",
    "brand_feedback",
    "brand_inferred",
    "audience_persona",
    "audience_simulation",
    "expert_strategy",
    "creator_manual",
    "external_reference",
}
RELATION_TYPES = {
    "responds_to",
    "supports",
    "opposes",
    "evidenced_by",
    "derived_from",
    "refines",
    "conflicts_with",
    "updates",
}


def build_rationale_node(
    *,
    project_id: str,
    node_type: str,
    title: str,
    content: str,
    source_type: str,
    source_perspective: str = "brand",
    layout: dict[str, float] | None = None,
    business_tags: list[str] | None = None,
    stance: str = "neutral",
    confidence: str = "medium",
    status: str = "open",
    created_by: str = "agent",
    based_on_script_version_id: str | None = None,
) -> dict[str, Any]:
    if node_type not in NODE_TYPES:
        raise ValueError("Invalid rationale node_type")
    if source_type not in SOURCE_TYPES:
        raise ValueError("Invalid rationale source_type")

    now = now_iso()
    return {
        "node_id": new_id("node"),
        "project_id": project_id,
        "node_type": node_type,
        "title": title.strip()[:120],
        "content": content.strip()[:2000],
        "source_type": source_type,
        "source_perspective": source_perspective,
        "business_tags": business_tags or [],
        "stance": stance,
        "confidence": confidence,
        "status": status,
        "in_consideration_queue": False,
        "in_negotiation_queue": False,
        "linked_script_refs": [],
        "related_reference_ids": [],
        "layout": layout or {"x": 160.0, "y": 120.0},
        "created_by": created_by,
        "updated_by": created_by,
        "based_on_script_version_id": based_on_script_version_id,
        "created_at": now,
        "updated_at": now,
    }


def _ibis_column(node_type: str) -> str:
    if node_type == "position":
        return "position"
    if node_type in {"argument", "reference"}:
        return "argument"
    return "issue"


def batch_is_issue_only(nodes: list[dict[str, Any]]) -> bool:
    return bool(nodes) and all(
        _ibis_column(str(node.get("node_type", "issue"))) == "issue" for node in nodes
    )


def validate_ibis_edge(from_node: dict[str, Any], to_node: dict[str, Any], relation_type: str) -> None:
    """Canonical storage: position→issue (responds_to), argument→position (supports/opposes).

    Issues may exist without any edges. Positions and arguments always require these links.
    """
    from_type = _ibis_column(str(from_node.get("node_type", "issue")))
    to_type = _ibis_column(str(to_node.get("node_type", "issue")))
    if from_type == "position" and to_type == "issue" and relation_type == "responds_to":
        return
    if from_type == "argument" and to_type == "position" and relation_type in {"supports", "opposes"}:
        return
    raise ValueError(
        "Invalid IBIS link: only position→issue (responds_to) or argument→position (supports/opposes) are allowed"
    )


def _positions_responding_to_issues(
    nodes_by_id: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> set[str]:
    linked: set[str] = set()
    for edge in edges:
        if edge.get("relation_type") != "responds_to":
            continue
        from_id = str(edge.get("from_node_id") or "")
        from_node = nodes_by_id.get(from_id)
        if not from_node or _ibis_column(str(from_node.get("node_type", "issue"))) != "position":
            continue
        to_node = nodes_by_id.get(str(edge.get("to_node_id") or ""))
        if to_node:
            validate_ibis_edge(from_node, to_node, "responds_to")
        linked.add(from_id)
    return linked


def _arguments_linked_to_positions(
    nodes_by_id: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> set[str]:
    linked: set[str] = set()
    for edge in edges:
        relation = edge.get("relation_type")
        if relation not in {"supports", "opposes"}:
            continue
        from_id = str(edge.get("from_node_id") or "")
        from_node = nodes_by_id.get(from_id)
        if not from_node or _ibis_column(str(from_node.get("node_type", "issue"))) != "argument":
            continue
        to_node = nodes_by_id.get(str(edge.get("to_node_id") or ""))
        if to_node:
            validate_ibis_edge(from_node, to_node, str(relation))
        linked.add(from_id)
    return linked


def _layout_y(node: dict[str, Any]) -> float:
    layout = node.get("layout")
    if isinstance(layout, dict):
        return float(layout.get("y", 0.0))
    return 0.0


def _argument_relation_type(node: dict[str, Any]) -> str:
    stance = str(node.get("stance") or "neutral").lower()
    if stance in {"con", "oppose", "opposed", "against", "negative"}:
        return "opposes"
    return "supports"


def auto_link_ibis_orphans(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    project_id: str,
    parent_issue_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Infer missing responds_to / supports / opposes edges for agent batches.

    LLM outputs often omit edges while still providing layout.y groupings. Uses
    parent_issue_ids for positions when issues are not in the same batch.
    """
    if not nodes:
        return edges

    nodes_by_id = {str(n["node_id"]): n for n in nodes if n.get("node_id")}
    positions_linked = _positions_responding_to_issues(nodes_by_id, edges)
    arguments_linked = _arguments_linked_to_positions(nodes_by_id, edges)

    seen = {
        (str(e.get("from_node_id")), str(e.get("to_node_id")), str(e.get("relation_type")))
        for e in edges
    }
    new_edges = list(edges)

    def append_edge(from_id: str, to_id: str, relation_type: str) -> None:
        key = (from_id, to_id, relation_type)
        if key in seen:
            return
        seen.add(key)
        new_edges.append(
            build_rationale_edge(
                project_id=project_id,
                from_node_id=from_id,
                to_node_id=to_id,
                relation_type=relation_type,
                created_by="agent",
            )
        )

    batch_issues = sorted(
        [n for n in nodes if _ibis_column(str(n.get("node_type", "issue"))) == "issue"],
        key=_layout_y,
    )
    issue_ids = [str(n["node_id"]) for n in batch_issues]
    for issue_id in parent_issue_ids or []:
        if issue_id and issue_id not in issue_ids:
            issue_ids.append(issue_id)

    positions = sorted(
        [n for n in nodes if _ibis_column(str(n.get("node_type", "issue"))) == "position"],
        key=_layout_y,
    )
    arguments = sorted(
        [n for n in nodes if _ibis_column(str(n.get("node_type", "issue"))) == "argument"],
        key=_layout_y,
    )

    orphan_positions = [p for p in positions if str(p["node_id"]) not in positions_linked]
    if orphan_positions and issue_ids:
        if len(issue_ids) == 1:
            target_issue = issue_ids[0]
            for position in orphan_positions:
                append_edge(str(position["node_id"]), target_issue, "responds_to")
        else:
            count = len(orphan_positions)
            bucket_count = len(issue_ids)
            for index, position in enumerate(orphan_positions):
                issue_index = min(index * bucket_count // count, bucket_count - 1)
                append_edge(str(position["node_id"]), issue_ids[issue_index], "responds_to")

    for argument in arguments:
        arg_id = str(argument["node_id"])
        if arg_id in arguments_linked:
            continue
        if not positions:
            continue
        best_position = min(positions, key=lambda pos: abs(_layout_y(pos) - _layout_y(argument)))
        append_edge(arg_id, str(best_position["node_id"]), _argument_relation_type(argument))

    return new_edges


def validate_ibis_graph_integrity(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    node_ids: set[str] | None = None,
    require_linked_for: Any | None = None,
) -> None:
    """Enforce IBIS parent links for positions and arguments.

    - Issue: may be a root with no positions or arguments (open question / backlog).
    - Position: must have responds_to → issue.
    - Argument: must have supports or opposes → position.

    By default only agent-created position/argument nodes are checked so users can
    add a node first and connect it on the canvas afterward.
    """
    if require_linked_for is None:
        require_linked_for = lambda node: node.get("created_by") != "user"

    nodes_by_id = {str(n["node_id"]): n for n in nodes if n.get("node_id")}
    check_ids = node_ids if node_ids is not None else set(nodes_by_id.keys())
    positions_linked = _positions_responding_to_issues(nodes_by_id, edges)
    arguments_linked = _arguments_linked_to_positions(nodes_by_id, edges)

    for node_id in check_ids:
        node = nodes_by_id.get(node_id)
        if not node or not require_linked_for(node):
            continue
        column = _ibis_column(str(node.get("node_type", "issue")))
        title = str(node.get("title") or node_id)
        if column == "position" and node_id not in positions_linked:
            raise ValueError(f"Position must respond to an Issue (responds_to): {title}")
        if column == "argument" and node_id not in arguments_linked:
            raise ValueError(f"Argument must support or oppose a Position: {title}")


def build_rationale_edge(
    *,
    project_id: str,
    from_node_id: str,
    to_node_id: str,
    relation_type: str,
    created_by: str = "agent",
) -> dict[str, Any]:
    if relation_type not in RELATION_TYPES:
        raise ValueError("Invalid rationale relation_type")
    return {
        "edge_id": new_id("edge"),
        "project_id": project_id,
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "relation_type": relation_type,
        "created_by": created_by,
        "created_at": now_iso(),
    }


def _index_by_id(items: list[dict], key: str) -> dict[str, dict]:
    return {item[key]: item for item in items if item.get(key)}


def merge_proposed_graph(
    *,
    project_id: str,
    existing_nodes: list[dict],
    existing_edges: list[dict],
    proposed_nodes: list[dict],
    proposed_edges: list[dict],
    replace_agent_sources: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Merge agent-proposed nodes/edges. Optionally drop prior agent nodes for given source_types."""
    kept_nodes = existing_nodes
    if replace_agent_sources:
        removed_ids = {
            node["node_id"]
            for node in existing_nodes
            if node.get("source_type") in replace_agent_sources and node.get("created_by") == "agent"
        }
        kept_nodes = [node for node in existing_nodes if node["node_id"] not in removed_ids]
        existing_edges = [
            edge
            for edge in existing_edges
            if edge.get("from_node_id") not in removed_ids and edge.get("to_node_id") not in removed_ids
        ]

    nodes_by_id = _index_by_id(kept_nodes, "node_id")
    edges: list[dict] = list(existing_edges)
    seen_edge_keys = {(e.get("from_node_id"), e.get("to_node_id"), e.get("relation_type")) for e in edges}

    for raw in proposed_nodes:
        node = dict(raw)
        if not node.get("node_id"):
            node["node_id"] = new_id("node")
        node.setdefault("project_id", project_id)
        node.setdefault("created_at", now_iso())
        node.setdefault("updated_at", node["created_at"])
        nodes_by_id[node["node_id"]] = node

    for raw in proposed_edges:
        edge = dict(raw)
        if not edge.get("edge_id"):
            edge["edge_id"] = new_id("edge")
        edge.setdefault("project_id", project_id)
        edge.setdefault("created_at", now_iso())
        from_node = nodes_by_id.get(str(edge.get("from_node_id") or ""))
        to_node = nodes_by_id.get(str(edge.get("to_node_id") or ""))
        if from_node and to_node:
            try:
                validate_ibis_edge(from_node, to_node, str(edge.get("relation_type") or ""))
            except ValueError:
                continue
        key = (edge.get("from_node_id"), edge.get("to_node_id"), edge.get("relation_type"))
        if key in seen_edge_keys:
            continue
        seen_edge_keys.add(key)
        edges.append(edge)

    merged_nodes = list(nodes_by_id.values())
    validate_ibis_graph_integrity(merged_nodes, edges)
    return merged_nodes, edges
