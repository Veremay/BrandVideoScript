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
SOURCE_PERSPECTIVES = {"brand", "audience", "creator", "expert", "system"}
STANCE_VALUES = {"support", "oppose", "neutral", "not_applicable", "pro", "con"}
CONFIDENCE_VALUES = {"high", "medium", "low"}
STATUS_VALUES = {
    "open",
    "in_review",
    "resolved",
    "needs_negotiation",
    "to_be_considered",
    "deferred",
    "dismissed",
}

# An Issue represents a question/topic; it must have at least this many responding
# Positions to be considered structurally complete by agent-generated nodes.
# User-created Issues are exempt from this check and may start empty.
MIN_ISSUE_POSITIONS = 1
MAX_CONSIDERATION_QUEUE_SIZE = 3


def count_consideration_positions(project: dict[str, Any]) -> int:
    queue = set(project.get("consideration_queue") or [])
    return sum(
        1
        for node in project.get("rationale_nodes", [])
        if node.get("node_type") == "position"
        and (node.get("in_consideration_queue") or node.get("node_id") in queue)
    )


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
    conflict_tags: list[str] | None = None,
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
    if not title.strip():
        raise ValueError("Rationale node title is required")
    if source_perspective not in SOURCE_PERSPECTIVES:
        raise ValueError("Invalid rationale source_perspective")
    if stance not in STANCE_VALUES:
        raise ValueError("Invalid rationale stance")
    if confidence not in CONFIDENCE_VALUES:
        raise ValueError("Invalid rationale confidence")
    if status not in STATUS_VALUES:
        raise ValueError("Invalid rationale status")

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
        # conflict_tags: uppercase-letter labels (A, B, C…) set by the Coordinator conflict
        # analysis to indicate that two or more Positions sharing a tag are in conflict.
        # Only meaningful on position nodes; empty list means no identified conflict.
        "conflict_tags": conflict_tags or [],
        "stance": stance,
        "confidence": confidence,
        "status": status,
        "in_consideration_queue": False,
        "in_negotiation_queue": False,
        # Position is on the creator's communication support list (feedback being argued).
        "in_communication_support_queue": False,
        "linked_script_refs": [],
        "related_reference_ids": [],
        "layout": layout or {"x": 160.0, "y": 120.0},
        "created_by": created_by,
        "updated_by": created_by,
        "based_on_script_version_id": based_on_script_version_id,
        # Reconcile lifecycle (bottom-up IBIS):
        #   lifecycle: active | resolved (issue no longer needs discussion) | superseded (replaced)
        #   change_mark: none | modified | new  (transient marker for the latest update)
        #   predecessor_id: id of the node this one replaced (modified)
        #   suggestion: non-binding hint for user-owned nodes (e.g. "resolved?" / "modify?")
        "lifecycle": "active",
        "change_mark": "none",
        "predecessor_id": None,
        "resolved_at": None,
        "suggestion": None,
        "created_at": now,
        "updated_at": now,
    }


def prune_singleton_conflict_tags(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop conflict tags that appear on fewer than 2 active positions.

    Nodes themselves are kept; only orphan/singleton conflict labels are cleared.
    Resolved/superseded positions do not count toward a tag's membership.
    """
    tag_counts: dict[str, int] = {}
    for node in nodes:
        if node.get("node_type") != "position":
            continue
        if node.get("lifecycle") in {"resolved", "superseded"}:
            continue
        for raw_tag in node.get("conflict_tags") or []:
            tag = str(raw_tag).strip()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    singleton_tags = {tag for tag, count in tag_counts.items() if count < 2}
    if not singleton_tags:
        return nodes

    pruned: list[dict[str, Any]] = []
    for node in nodes:
        tags = node.get("conflict_tags") or []
        if node.get("node_type") != "position" or not tags:
            pruned.append(node)
            continue
        kept = [tag for tag in tags if str(tag).strip() not in singleton_tags]
        if kept == list(tags):
            pruned.append(node)
        else:
            pruned.append({**node, "conflict_tags": kept})
    return pruned


def _ibis_column(node_type: str) -> str:
    if node_type == "position":
        return "position"
    if node_type in {"argument", "reference"}:
        return "argument"
    return "issue"


def validate_ibis_edge(from_node: dict[str, Any], to_node: dict[str, Any], relation_type: str) -> None:
    """Canonical IBIS edge rules:

    - position → issue (``responds_to``): a stance addresses a question/topic.
    - position ↔ position (``conflicts_with``): legacy edge, retained for backward
      compatibility but no longer actively generated; conflict is now expressed via
      ``conflict_tags`` on position nodes.
    - argument → position (``supports`` / ``opposes``).

    Positions express stances but must be carried by Issues. Issues are topics
    that questions are raised around, and arguments always link to a position.
    """
    from_type = _ibis_column(str(from_node.get("node_type", "issue")))
    to_type = _ibis_column(str(to_node.get("node_type", "issue")))
    if from_type == "position" and to_type == "issue" and relation_type == "responds_to":
        return
    if from_type == "position" and to_type == "position" and relation_type == "conflicts_with":
        return
    if from_type == "argument" and to_type == "position" and relation_type in {"supports", "opposes"}:
        return
    raise ValueError(
        "Invalid IBIS link: only position→issue (responds_to), position↔position (conflicts_with), "
        "or argument→position (supports/opposes) are allowed"
    )


def _issue_responding_positions(
    nodes_by_id: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, set[str]]:
    """Map each issue id to the set of position ids that ``responds_to`` it."""
    result: dict[str, set[str]] = {}
    for edge in edges:
        if edge.get("relation_type") != "responds_to":
            continue
        from_id = str(edge.get("from_node_id") or "")
        to_id = str(edge.get("to_node_id") or "")
        from_node = nodes_by_id.get(from_id)
        to_node = nodes_by_id.get(to_id)
        if not from_node or not to_node:
            continue
        if _ibis_column(str(from_node.get("node_type", "issue"))) != "position":
            continue
        if _ibis_column(str(to_node.get("node_type", "issue"))) != "issue":
            continue
        result.setdefault(to_id, set()).add(from_id)
    return result


def _position_responding_issues(
    nodes_by_id: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, set[str]]:
    """Map each position id to the set of issue ids it ``responds_to``."""
    result: dict[str, set[str]] = {}
    for edge in edges:
        if edge.get("relation_type") != "responds_to":
            continue
        from_id = str(edge.get("from_node_id") or "")
        to_id = str(edge.get("to_node_id") or "")
        from_node = nodes_by_id.get(from_id)
        to_node = nodes_by_id.get(to_id)
        if not from_node or not to_node:
            continue
        if _ibis_column(str(from_node.get("node_type", "issue"))) != "position":
            continue
        if _ibis_column(str(to_node.get("node_type", "issue"))) != "issue":
            continue
        result.setdefault(from_id, set()).add(to_id)
    return result


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


def _position_supporting_arguments(
    nodes_by_id: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, set[str]]:
    """Map each position id to supporting/opposing argument ids."""
    result: dict[str, set[str]] = {}
    for edge in edges:
        if edge.get("relation_type") not in {"supports", "opposes"}:
            continue
        from_id = str(edge.get("from_node_id") or "")
        to_id = str(edge.get("to_node_id") or "")
        from_node = nodes_by_id.get(from_id)
        to_node = nodes_by_id.get(to_id)
        if not from_node or not to_node:
            continue
        if _ibis_column(str(from_node.get("node_type", "issue"))) != "argument":
            continue
        if _ibis_column(str(to_node.get("node_type", "issue"))) != "position":
            continue
        result.setdefault(to_id, set()).add(from_id)
    return result


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
) -> list[dict[str, Any]]:
    """Infer missing argument → position edges for agent batches.

    Positions must be carried by Issues, so they are never auto-linked here.
    Issues are decision-question containers that agents
    must wire up explicitly with ``responds_to`` positions. Only Arguments, which are
    meaningless without a Position, are auto-attached to the nearest one by
    ``layout.y`` when the LLM omits the edge.
    """
    if not nodes:
        return edges

    nodes_by_id = {str(n["node_id"]): n for n in nodes if n.get("node_id")}
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

    positions = sorted(
        [n for n in nodes if _ibis_column(str(n.get("node_type", "issue"))) == "position"],
        key=_layout_y,
    )
    arguments = sorted(
        [n for n in nodes if _ibis_column(str(n.get("node_type", "issue"))) == "argument"],
        key=_layout_y,
    )

    for argument in arguments:
        arg_id = str(argument["node_id"])
        if arg_id in arguments_linked:
            continue
        if not positions:
            continue
        best_position = min(positions, key=lambda pos: abs(_layout_y(pos) - _layout_y(argument)))
        append_edge(arg_id, str(best_position["node_id"]), _argument_relation_type(argument))

    return new_edges


def drop_agent_issues_without_positions(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    issue_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    """Remove agent Issues that no longer have any responding Positions.

    User-created Issues are kept even when empty. Resolved Issues are kept for history.
    """
    if not issue_ids:
        return nodes, edges, set()

    nodes_by_id = {str(n["node_id"]): n for n in nodes if n.get("node_id")}
    issue_positions = _issue_responding_positions(nodes_by_id, edges)
    to_drop: set[str] = set()
    for issue_id in issue_ids:
        issue = nodes_by_id.get(issue_id)
        if not issue or _ibis_column(str(issue.get("node_type", "issue"))) != "issue":
            continue
        if issue.get("lifecycle") == "resolved":
            continue
        if issue.get("created_by") == "user":
            continue
        if len(issue_positions.get(issue_id, set())) < MIN_ISSUE_POSITIONS:
            to_drop.add(issue_id)

    if not to_drop:
        return nodes, edges, set()

    next_nodes = [n for n in nodes if n.get("node_id") not in to_drop]
    next_edges = [
        e
        for e in edges
        if e.get("from_node_id") not in to_drop and e.get("to_node_id") not in to_drop
    ]
    return next_nodes, next_edges, to_drop


def prune_orphan_agent_issues(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    """Drop agent Issues with no responding Positions; keep user/resolved Issues."""
    issue_ids = {
        str(n["node_id"])
        for n in nodes
        if n.get("node_id") and _ibis_column(str(n.get("node_type", "issue"))) == "issue"
    }
    return drop_agent_issues_without_positions(nodes, edges, issue_ids)


def prune_orphan_positions(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    """Drop agent Positions that have no supporting/opposing Arguments.

    User-created Positions are kept even when orphaned.
    Returns (cleaned_nodes, cleaned_edges, dropped_position_ids).
    """
    nodes_by_id = {str(n["node_id"]): n for n in nodes if n.get("node_id")}
    # Map position_id -> set of argument_ids that link to it
    position_arguments: dict[str, set[str]] = {}
    for edge in edges:
        rel = str(edge.get("relation_type") or "")
        if rel not in {"supports", "opposes"}:
            continue
        to_id = str(edge.get("to_node_id") or "")
        from_id = str(edge.get("from_node_id") or "")
        to_node = nodes_by_id.get(to_id)
        if to_node and _ibis_column(str(to_node.get("node_type", ""))) == "position":
            position_arguments.setdefault(to_id, set()).add(from_id)

    to_drop: set[str] = set()
    for pos_id, pos in nodes_by_id.items():
        if _ibis_column(str(pos.get("node_type", ""))) != "position":
            continue
        if pos.get("created_by") == "user":
            continue
        if not position_arguments.get(pos_id):
            to_drop.add(pos_id)

    if not to_drop:
        return nodes, edges, set()

    next_nodes = [n for n in nodes if n.get("node_id") not in to_drop]
    next_edges = [
        e
        for e in edges
        if e.get("from_node_id") not in to_drop and e.get("to_node_id") not in to_drop
    ]
    return next_nodes, next_edges, to_drop


def collect_issue_delete_cascade(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    issue_id: str,
) -> set[str]:
    """Issue plus Positions that respond to it and Arguments linked to those Positions."""
    ids: set[str] = {issue_id}
    position_ids: set[str] = set()
    for edge in edges:
        if edge.get("relation_type") != "responds_to":
            continue
        if str(edge.get("to_node_id") or "") != issue_id:
            continue
        pos_id = str(edge.get("from_node_id") or "")
        pos = nodes_by_id.get(pos_id)
        if pos and str(pos.get("node_type")) == "position":
            position_ids.add(pos_id)
            ids.add(pos_id)
    for edge in edges:
        if edge.get("relation_type") not in {"supports", "opposes"}:
            continue
        if str(edge.get("to_node_id") or "") not in position_ids:
            continue
        arg_id = str(edge.get("from_node_id") or "")
        arg = nodes_by_id.get(arg_id)
        if arg and str(arg.get("node_type")) == "argument":
            ids.add(arg_id)
    return ids


def collect_position_delete_cascade(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    position_id: str,
) -> set[str]:
    """Position plus Arguments that support or oppose it."""
    ids: set[str] = {position_id}
    for edge in edges:
        if edge.get("relation_type") not in {"supports", "opposes"}:
            continue
        if str(edge.get("to_node_id") or "") != position_id:
            continue
        arg_id = str(edge.get("from_node_id") or "")
        arg = nodes_by_id.get(arg_id)
        if arg and str(arg.get("node_type")) == "argument":
            ids.add(arg_id)
    return ids


def collect_argument_delete_cascade(
    nodes_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    argument_id: str,
) -> set[str]:
    """Argument deletion is local; it does not cascade to its Position."""
    argument = nodes_by_id.get(argument_id)
    if argument and str(argument.get("node_type")) == "argument":
        return {argument_id}
    return set()


def prune_orphan_arguments(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Remove Argument nodes that are not connected to any Position via supports/opposes.

    This can happen after reconcile pruning removes Positions that were the only
    target of an Argument. Rather than crashing the whole graph merge, we drop the
    orphan Argument silently.
    """
    nodes_by_id = _index_by_id(nodes, "node_id")
    # Collect argument IDs that are linked to at least one Position
    linked_arg_ids: set[str] = set()
    position_ids: set[str] = {
        str(n["node_id"]) for n in nodes if n.get("node_type") == "position" and n.get("node_id")
    }
    for edge in edges:
        if edge.get("relation_type") not in {"supports", "opposes"}:
            continue
        to_id = str(edge.get("to_node_id") or "")
        from_id = str(edge.get("from_node_id") or "")
        if to_id in position_ids:
            arg = nodes_by_id.get(from_id)
            if arg and str(arg.get("node_type")) == "argument":
                linked_arg_ids.add(from_id)

    orphan_ids: set[str] = set()
    for node in nodes:
        if node.get("node_type") != "argument":
            continue
        node_id = str(node.get("node_id") or "")
        if not node_id:
            continue
        if node_id not in linked_arg_ids:
            orphan_ids.add(node_id)

    if orphan_ids:
        kept_nodes = [n for n in nodes if str(n.get("node_id") or "") not in orphan_ids]
        kept_edges = [
            e for e in edges
            if str(e.get("from_node_id") or "") not in orphan_ids
            and str(e.get("to_node_id") or "") not in orphan_ids
        ]
        return kept_nodes, kept_edges
    return nodes, edges


def validate_ibis_graph_integrity(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    node_ids: set[str] | None = None,
    require_linked_for: Any | None = None,
) -> None:
    """Enforce IBIS structural rules.

    - Position: must respond to an Issue and have at least one Argument.
    - Issue: represents a question/topic; agent-created issues must have at least
      ``MIN_ISSUE_POSITIONS`` position(s) via ``responds_to``. User-created issues
      may start empty while the user adds positions.
    - Argument: must support or oppose a position.

    By default only agent-created nodes are checked so users can add a node first
    and connect it on the canvas afterward.
    """
    if require_linked_for is None:
        require_linked_for = lambda node: node.get("created_by") != "user"

    nodes_by_id = {str(n["node_id"]): n for n in nodes if n.get("node_id")}
    check_ids = node_ids if node_ids is not None else set(nodes_by_id.keys())
    arguments_linked = _arguments_linked_to_positions(nodes_by_id, edges)
    issue_positions = _issue_responding_positions(nodes_by_id, edges)
    position_issues = _position_responding_issues(nodes_by_id, edges)
    position_arguments = _position_supporting_arguments(nodes_by_id, edges)

    for node_id in check_ids:
        node = nodes_by_id.get(node_id)
        if not node or not require_linked_for(node):
            continue
        column = _ibis_column(str(node.get("node_type", "issue")))
        title = str(node.get("title") or node_id)
        if not str(node.get("title") or "").strip():
            raise ValueError(f"Rationale node title is required: {node_id}")
        # Resolved Issues are intentionally retained as history; their decision
        # question no longer needs discussion, so linked-position requirements no
        # longer apply to them.
        if column == "issue" and node.get("lifecycle") == "resolved":
            continue
        if column == "position" and not position_issues.get(node_id):
            raise ValueError(f"Position must respond to an Issue: {title}")
        if column == "position" and not position_arguments.get(node_id):
            raise ValueError(f"Position must have at least one Argument: {title}")
        if column == "issue" and len(issue_positions.get(node_id, set())) < MIN_ISSUE_POSITIONS:
            raise ValueError(
                f"Issue must have at least {MIN_ISSUE_POSITIONS} Position(s) responding to it "
                f"(responds_to); it cannot exist alone as an agent node: {title}"
            )
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
        node.setdefault("lifecycle", "active")
        node.setdefault("change_mark", "none")
        node.setdefault("predecessor_id", None)
        node.setdefault("resolved_at", None)
        node.setdefault("suggestion", None)
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
    merged_nodes, edges, _ = prune_orphan_agent_issues(merged_nodes, edges)
    merged_nodes, edges, _ = prune_orphan_positions(merged_nodes, edges)
    # Re-run after pruning positions — removing a Position may leave its Issue orphaned
    merged_nodes, edges, _ = prune_orphan_agent_issues(merged_nodes, edges)
    # Remove Arguments that lost their Position during pruning
    merged_nodes, edges = prune_orphan_arguments(merged_nodes, edges)
    validate_ibis_graph_integrity(merged_nodes, edges)
    return merged_nodes, edges


# --- Reconcile: anchored re-evaluation on "update map" ----------------------


def _reset_change_marks(nodes: list[dict[str, Any]]) -> None:
    """Clear transient per-update markers before a fresh reconcile pass."""
    for node in nodes:
        if node.get("change_mark") not in (None, "none"):
            node["change_mark"] = "none"
        node["suggestion"] = None


def supersede_node(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    old_id: str,
    *,
    new_title: str | None = None,
    new_content: str | None = None,
) -> str | None:
    """Replace node ``old_id`` with a fresh node (new id) that inherits every edge
    of the old node, then drop the old node and its original edges from the live
    graph (the old version survives only in the pre-update snapshot — Option B).

    Returns the new node id, or ``None`` if ``old_id`` does not exist. Mutates
    ``nodes`` and ``edges`` in place.
    """
    by_id = _index_by_id(nodes, "node_id")
    old = by_id.get(old_id)
    if old is None:
        return None

    new_node = dict(old)
    new_node["node_id"] = new_id("node")
    new_node["predecessor_id"] = old_id
    new_node["change_mark"] = "modified"
    new_node["lifecycle"] = "active"
    new_node["resolved_at"] = None
    new_node["suggestion"] = None
    if new_title is not None:
        new_node["title"] = str(new_title).strip()[:120]
    if new_content is not None:
        new_node["content"] = str(new_content).strip()[:2000]
    new_node["updated_by"] = "agent"
    new_node["updated_at"] = now_iso()

    inherited: list[dict[str, Any]] = []
    for edge in edges:
        if edge.get("from_node_id") != old_id and edge.get("to_node_id") != old_id:
            inherited.append(edge)
            continue
        clone = dict(edge)
        clone["edge_id"] = new_id("edge")
        if clone.get("from_node_id") == old_id:
            clone["from_node_id"] = new_node["node_id"]
        if clone.get("to_node_id") == old_id:
            clone["to_node_id"] = new_node["node_id"]
        inherited.append(clone)

    edges[:] = inherited
    nodes[:] = [n for n in nodes if n.get("node_id") != old_id]
    nodes.append(new_node)
    return new_node["node_id"]


def resolve_issue(nodes: list[dict[str, Any]], issue_id: str) -> bool:
    """Mark an Issue as resolved. Keeps its id and its edges."""
    issue = _index_by_id(nodes, "node_id").get(issue_id)
    if issue is None or _ibis_column(str(issue.get("node_type", "issue"))) != "issue":
        return False
    if issue.get("lifecycle") != "resolved":
        issue["lifecycle"] = "resolved"
        issue["resolved_at"] = now_iso()
        issue["updated_at"] = now_iso()
    issue["change_mark"] = "none"
    return True


def revive_issue(nodes: list[dict[str, Any]], issue_id: str) -> bool:
    """Reactivate a previously resolved Issue when its conflict returns."""
    issue = _index_by_id(nodes, "node_id").get(issue_id)
    if issue is None:
        return False
    if issue.get("lifecycle") == "resolved":
        issue["lifecycle"] = "active"
        issue["resolved_at"] = None
        issue["updated_at"] = now_iso()
    return True


def _assign_new_ids(raw_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for raw in raw_nodes:
        node = dict(raw)
        if not node.get("node_id"):
            node["node_id"] = new_id("node")
        prepared.append(node)
    return prepared


def _chase_remap(remap: dict[str, str], node_id: str | None) -> str | None:
    seen: set[str] = set()
    current = node_id
    while current in remap and current not in seen:
        seen.add(current)
        current = remap[current]
    return current


def apply_reconcile(
    *,
    project_id: str,
    existing_nodes: list[dict[str, Any]],
    existing_edges: list[dict[str, Any]],
    issue_reviews: list[dict[str, Any]] | None = None,
    node_modifications: list[dict[str, Any]] | None = None,
    new_nodes: list[dict[str, Any]] | None = None,
    new_edges: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply an anchored re-evaluation result to the live graph.

    Inputs (all optional):
    - ``issue_reviews``: ``[{issue_id, verdict: still_holds|resolved|modified,
      new_title?, new_content?, reason?}]`` — Expert's verdict per existing Issue.
    - ``node_modifications``: ``[{node_id, new_title?, new_content?, reason?}]`` —
      substantive content changes for Position/Argument nodes.
    - ``new_nodes`` / ``new_edges``: freshly emerged conflicts/positions.

    Rules: ids never change for ``still_holds``/``resolved``; ``modified`` replaces
    the node with a new id that inherits its edges (old node dropped, kept in the
    snapshot). User-owned nodes are never mutated — they only receive a
    non-binding ``suggestion`` flag. New nodes are tagged ``change_mark="new"``.
    """
    nodes: list[dict[str, Any]] = [dict(n) for n in existing_nodes]
    edges: list[dict[str, Any]] = [dict(e) for e in existing_edges]
    _reset_change_marks(nodes)
    by_id = _index_by_id(nodes, "node_id")
    id_remap: dict[str, str] = {}

    def _is_user(node: dict[str, Any] | None) -> bool:
        return bool(node) and node.get("created_by") == "user"

    for review in issue_reviews or []:
        issue_id = str(review.get("issue_id") or "")
        verdict = str(review.get("verdict") or "still_holds")
        node = by_id.get(issue_id)
        if node is None:
            continue
        if _is_user(node):
            if verdict == "resolved":
                node["suggestion"] = "resolved?"
            elif verdict == "modified":
                node["suggestion"] = "modify?"
            continue
        if verdict == "resolved":
            resolve_issue(nodes, issue_id)
        elif verdict == "modified":
            new_nid = supersede_node(
                nodes,
                edges,
                issue_id,
                new_title=review.get("new_title"),
                new_content=review.get("new_content"),
            )
            if new_nid:
                id_remap[issue_id] = new_nid
                by_id = _index_by_id(nodes, "node_id")
        else:
            revive_issue(nodes, issue_id)

    for mod in node_modifications or []:
        node_id = str(mod.get("node_id") or "")
        node = by_id.get(node_id)
        if node is None:
            continue
        if _is_user(node):
            node["suggestion"] = "modify?"
            continue
        new_nid = supersede_node(
            nodes,
            edges,
            node_id,
            new_title=mod.get("new_title"),
            new_content=mod.get("new_content"),
        )
        if new_nid:
            id_remap[node_id] = new_nid
            by_id = _index_by_id(nodes, "node_id")

    prepared_nodes = _assign_new_ids(new_nodes or [])
    new_node_ids = {n["node_id"] for n in prepared_nodes}
    remapped_edges: list[dict[str, Any]] = []
    for raw in new_edges or []:
        edge = dict(raw)
        edge["from_node_id"] = _chase_remap(id_remap, edge.get("from_node_id"))
        edge["to_node_id"] = _chase_remap(id_remap, edge.get("to_node_id"))
        remapped_edges.append(edge)

    nodes, edges = merge_proposed_graph(
        project_id=project_id,
        existing_nodes=nodes,
        existing_edges=edges,
        proposed_nodes=prepared_nodes,
        proposed_edges=remapped_edges,
    )
    for node in nodes:
        if node.get("node_id") in new_node_ids:
            node["change_mark"] = "new"
    return nodes, edges
