from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.rationale_ops import (
    RELATION_TYPES,
    SOURCE_TYPES,
    auto_link_ibis_orphans,
    batch_is_issue_only,
    build_rationale_edge,
    build_rationale_node,
    validate_ibis_edge,
    validate_ibis_graph_integrity,
)
from app.services.pipeline_log import log_step
from app.models.script import now_iso


@dataclass
class PersistedIbisGraph:
    """Result of persist_rationale_graph tool — validated nodes/edges ready for merge."""

    proposed_nodes: list[dict[str, Any]] = field(default_factory=list)
    proposed_edges: list[dict[str, Any]] = field(default_factory=list)
    node_updates: list[dict[str, Any]] = field(default_factory=list)


def persist_rationale_graph(
    project_id: str,
    ibis: dict[str, Any] | None,
    *,
    script_version_id: str | None = None,
    allowed_source_types: set[str] | None = None,
    parent_issue_ids: list[str] | None = None,
) -> PersistedIbisGraph:
    """
    Tool: validate LLM-proposed IBIS payload and materialize server-side node/edge documents.
    Agents must not invent node_id; the backend assigns IDs here.
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
        source_type = str(raw.get("source_type", "expert_strategy"))
        if source_type not in SOURCE_TYPES:
            source_type = "expert_strategy"
        if allowed_source_types and source_type not in allowed_source_types:
            continue
        node = build_rationale_node(
            project_id=project_id,
            node_type=str(raw.get("node_type", "issue")),
            title=str(raw.get("title") or "未命名节点"),
            content=str(raw.get("content") or ""),
            source_type=source_type,
            source_perspective=str(raw.get("source_perspective") or "expert"),
            business_tags=list(raw.get("business_tags") or []),
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

    if batch_is_issue_only(built_nodes) and ibis.get("edges"):
        log_step(
            "persist_rationale_graph.ignore_issue_edges",
            phase="OUT",
            project_id=project_id,
            skipped=len(ibis.get("edges") or []),
        )

    edge_specs = [] if batch_is_issue_only(built_nodes) else (ibis.get("edges") or [])
    for raw in edge_specs:
        if not isinstance(raw, dict):
            continue
        from_index = int(raw.get("from_index", -1))
        to_index = int(raw.get("to_index", -1))
        if 0 <= from_index < len(built_nodes) and 0 <= to_index < len(built_nodes):
            add_edge(
                built_nodes[from_index]["node_id"],
                built_nodes[to_index]["node_id"],
                str(raw.get("relation_type") or "responds_to"),
            )

    for raw in ibis.get("external_edges") or []:
        if not isinstance(raw, dict):
            continue
        from_index = int(raw.get("from_index", -1))
        to_node_id = str(raw.get("to_node_id") or "")
        if 0 <= from_index < len(built_nodes) and to_node_id:
            add_edge(
                built_nodes[from_index]["node_id"],
                to_node_id,
                str(raw.get("relation_type") or "responds_to"),
            )

    edge_count_before = len(built_edges)
    built_edges = auto_link_ibis_orphans(
        built_nodes,
        built_edges,
        project_id=project_id,
        parent_issue_ids=parent_issue_ids,
    )
    if len(built_edges) > edge_count_before:
        log_step(
            "persist_rationale_graph.auto_link",
            phase="OUT",
            project_id=project_id,
            edges_added=len(built_edges) - edge_count_before,
        )

    updates = [
        u for u in (ibis.get("node_updates") or []) if isinstance(u, dict) and u.get("node_id")
    ]
    if built_nodes:
        batch_ids = {n["node_id"] for n in built_nodes}
        validate_ibis_graph_integrity(
            built_nodes,
            built_edges,
            node_ids=batch_ids,
            require_linked_for=lambda _node: True,
        )
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
