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


def validate_ibis_edge(from_node: dict[str, Any], to_node: dict[str, Any], relation_type: str) -> None:
    """Canonical storage: position→issue (responds_to), argument→position (supports/opposes)."""
    from_type = _ibis_column(str(from_node.get("node_type", "issue")))
    to_type = _ibis_column(str(to_node.get("node_type", "issue")))
    if from_type == "position" and to_type == "issue" and relation_type == "responds_to":
        return
    if from_type == "argument" and to_type == "position" and relation_type in {"supports", "opposes"}:
        return
    raise ValueError(
        "Invalid IBIS link: only position→issue (responds_to) or argument→position (supports/opposes) are allowed"
    )


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
        key = (edge.get("from_node_id"), edge.get("to_node_id"), edge.get("relation_type"))
        if key in seen_edge_keys:
            continue
        seen_edge_keys.add(key)
        edges.append(edge)

    return list(nodes_by_id.values()), edges
