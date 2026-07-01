from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.rationale_ops import (
    RELATION_TYPES,
    SOURCE_TYPES,
    auto_link_ibis_orphans,
    build_rationale_edge,
    build_rationale_node,
    validate_ibis_edge,
)
from app.services.pipeline_log import log_step
from app.models.script import now_iso


@dataclass
class PersistedIbisGraph:
    """Result of persist_rationale_graph tool — validated nodes/edges ready for merge."""

    proposed_nodes: list[dict[str, Any]] = field(default_factory=list)
    proposed_edges: list[dict[str, Any]] = field(default_factory=list)
    node_updates: list[dict[str, Any]] = field(default_factory=list)


def _resolve_spec_node_id(
    spec: dict[str, Any],
    built_nodes: list[dict[str, Any]],
    index_key: str,
    id_key: str,
) -> str | None:
    """Resolve an edge endpoint that may reference a batch index or an existing node id.

    ``index_key`` (e.g. ``from_index``) points into this batch's ``nodes`` array;
    ``id_key`` (e.g. ``from_node_id``) references an already-persisted node. This
    lets agents wire existing Positions into a freshly created decision Issue.
    """
    raw_index = spec.get(index_key)
    if isinstance(raw_index, bool):
        raw_index = None
    if raw_index is not None:
        try:
            idx = int(raw_index)
        except (TypeError, ValueError):
            return None
        if 0 <= idx < len(built_nodes):
            return str(built_nodes[idx]["node_id"])
        return None
    node_id = spec.get(id_key)
    return str(node_id) if node_id else None


def persist_rationale_graph(
    project_id: str,
    ibis: dict[str, Any] | None,
    *,
    script_version_id: str | None = None,
    allowed_source_types: set[str] | None = None,
    allow_unlinked_positions: bool = False,
) -> PersistedIbisGraph:
    """
    Tool: validate LLM-proposed IBIS payload and materialize server-side node/edge documents.
    Agents must not invent node_id; the backend assigns IDs here.

    Edge endpoints (``edges`` and ``external_edges``) accept either a batch index
    (``from_index`` / ``to_index``) or an existing node id (``from_node_id`` /
    ``to_node_id``), so decision Issues can link Positions created by other agents.
    Structural completeness (an agent-created Issue needs at least one responding
    Position, a Position needs an Issue, and an Argument needs a Position) is
    enforced later during the full-graph merge. Some agent steps may opt into
    ``allow_unlinked_positions`` because the orchestrator adds carrier Issues
    after Coordinator conflict analysis.
    """
    if not ibis:
        return PersistedIbisGraph()

    raw_nodes = ibis.get("nodes") or []
    if not isinstance(raw_nodes, list):
        raise ValueError("ibis.nodes must be a list")

    built_nodes: list[dict[str, Any]] = []
    for raw in raw_nodes:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        source_type = str(raw.get("source_type", "expert_strategy"))
        if source_type not in SOURCE_TYPES:
            source_type = "expert_strategy"
        if allowed_source_types and source_type not in allowed_source_types:
            continue
        raw_conflict_tags = raw.get("conflict_tags")
        node = build_rationale_node(
            project_id=project_id,
            node_type=str(raw.get("node_type", "issue")),
            title=title,
            content=str(raw.get("content") or ""),
            source_type=source_type,
            source_perspective=str(raw.get("source_perspective") or "expert"),
            business_tags=list(raw.get("business_tags") or []),
            conflict_tags=list(raw_conflict_tags) if isinstance(raw_conflict_tags, list) else None,
            stance=str(raw.get("stance") or "neutral"),
            confidence=str(raw.get("confidence") or "medium"),
            status=str(raw.get("status") or "open"),
            created_by="agent",
            based_on_script_version_id=script_version_id,
            layout=raw.get("layout") if isinstance(raw.get("layout"), dict) else None,
        )
        refs = raw.get("linked_script_refs")
        if isinstance(refs, list):
            node["linked_script_refs"] = refs
        built_nodes.append(node)

    built_edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_edge(from_id: str, to_id: str, relation: str) -> None:
        if relation not in RELATION_TYPES:
            relation = "responds_to"
        from_node = next((n for n in built_nodes if n["node_id"] == from_id), None)
        to_node = next((n for n in built_nodes if n["node_id"] == to_id), None)
        if from_node and to_node:
            try:
                validate_ibis_edge(from_node, to_node, relation)
            except ValueError as exc:
                log_step(
                    "persist_rationale_graph.skip_edge",
                    phase="OUT",
                    project_id=project_id,
                    from_node_id=from_id,
                    to_node_id=to_id,
                    relation_type=relation,
                    reason=str(exc),
                )
                return
        key = (from_id, to_id, relation)
        if key in seen:
            return
        seen.add(key)
        built_edges.append(
            build_rationale_edge(
                project_id=project_id,
                from_node_id=from_id,
                to_node_id=to_id,
                relation_type=relation,
                created_by="agent",
            )
        )

    for raw in [*(ibis.get("edges") or []), *(ibis.get("external_edges") or [])]:
        if not isinstance(raw, dict):
            continue
        from_id = _resolve_spec_node_id(raw, built_nodes, "from_index", "from_node_id")
        to_id = _resolve_spec_node_id(raw, built_nodes, "to_index", "to_node_id")
        if from_id and to_id:
            add_edge(from_id, to_id, str(raw.get("relation_type") or "responds_to"))

    edge_count_before = len(built_edges)
    built_edges = auto_link_ibis_orphans(
        built_nodes,
        built_edges,
        project_id=project_id,
    )
    if len(built_edges) > edge_count_before:
        log_step(
            "persist_rationale_graph.auto_link",
            phase="OUT",
            project_id=project_id,
            edges_added=len(built_edges) - edge_count_before,
        )

    issue_titles_before = {
        str(n["node_id"]): str(n.get("title") or n["node_id"])
        for n in built_nodes
        if n.get("node_id") and str(n.get("node_type") or "") == "issue"
    }
    built_node_ids_before = {str(n.get("node_id")) for n in built_nodes if n.get("node_id")}
    issue_ids_with_responding_edges = {
        str(edge.get("to_node_id"))
        for edge in built_edges
        if edge.get("relation_type") == "responds_to" and edge.get("to_node_id")
    }
    position_ids_with_issue_edges = {
        str(edge.get("from_node_id"))
        for edge in built_edges
        if edge.get("relation_type") == "responds_to" and edge.get("from_node_id")
    }
    argument_ids_with_position_edges = {
        str(edge.get("from_node_id"))
        for edge in built_edges
        if edge.get("relation_type") in {"supports", "opposes"} and edge.get("from_node_id")
    }
    built_nodes = [
        node
        for node in built_nodes
        if (
            (
                str(node.get("node_type") or "") == "issue"
                and (
                    str(node.get("node_id") or "") in issue_ids_with_responding_edges
                    or node.get("created_by") == "user"
                )
            )
            or (
                str(node.get("node_type") or "") == "position"
                and (
                    allow_unlinked_positions
                    or str(node.get("node_id") or "") in position_ids_with_issue_edges
                )
            )
            or (
                str(node.get("node_type") or "") in {"argument", "reference"}
                and str(node.get("node_id") or "") in argument_ids_with_position_edges
            )
        )
    ]
    kept_node_ids = {str(n.get("node_id")) for n in built_nodes if n.get("node_id")}
    dropped_node_ids = built_node_ids_before - kept_node_ids
    kept_issue_ids = {
        str(n.get("node_id"))
        for n in built_nodes
        if n.get("node_id") and str(n.get("node_type") or "") == "issue"
    }
    dropped_issue_ids = set(issue_titles_before) - kept_issue_ids
    built_edges = [
        edge
        for edge in built_edges
        if (
            str(edge.get("from_node_id") or "") not in dropped_node_ids
            and str(edge.get("to_node_id") or "") not in dropped_node_ids
        )
    ]
    if dropped_issue_ids:
        log_step(
            "persist_rationale_graph.drop_orphan_issues",
            phase="WARN",
            project_id=project_id,
            dropped_count=len(dropped_issue_ids),
            dropped_titles=[issue_titles_before[i] for i in sorted(dropped_issue_ids) if i in issue_titles_before],
        )

    updates = [
        u for u in (ibis.get("node_updates") or []) if isinstance(u, dict) and u.get("node_id")
    ]
    return PersistedIbisGraph(
        proposed_nodes=built_nodes,
        proposed_edges=built_edges,
        node_updates=updates,
    )


def apply_node_updates(
    nodes: list[dict[str, Any]],
    updates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    update_map = {u["node_id"]: u for u in updates if u.get("node_id")}
    if not update_map:
        return nodes

    result: list[dict[str, Any]] = []
    for node in nodes:
        node_id = node.get("node_id")
        if node.get("created_by") == "user" or node_id not in update_map:
            result.append(node)
            continue
        patch = update_map[node_id]
        result.append(
            {
                **node,
                **{k: v for k, v in patch.items() if k != "node_id" and v is not None},
                "updated_by": "agent",
                "updated_at": now_iso(),
            }
        )
    return result
