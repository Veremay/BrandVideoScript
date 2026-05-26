from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.artifact_stale import stale_set_fields
from app.models.rationale_ops import build_rationale_edge, build_rationale_node, validate_ibis_edge
from app.models.script import now_iso
from app.repositories.projects import get_project


async def create_graph_node(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    node_type: str,
    title: str,
    content: str,
    source_type: str = "creator_manual",
    source_perspective: str = "creator",
    layout: dict[str, float] | None = None,
    status: str = "open",
    linked_script_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    node = build_rationale_node(
        project_id=project_id,
        node_type=node_type,
        title=title,
        content=content,
        source_type=source_type,
        source_perspective=source_perspective,
        layout=layout,
        status=status,
        created_by="user",
    )
    if linked_script_refs:
        node["linked_script_refs"] = linked_script_refs

    nodes = [*project.get("rationale_nodes", []), node]
    await _write_graph(db, project_id, user_id, nodes=nodes, edges=project.get("rationale_edges", []))
    return node


async def update_graph_node(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    node_id: str,
    changes: dict[str, Any],
) -> dict[str, Any] | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    nodes = project.get("rationale_nodes", [])
    updated: dict[str, Any] | None = None
    next_nodes: list[dict] = []
    for node in nodes:
        if node.get("node_id") != node_id:
            next_nodes.append(node)
            continue
        updated = {**node, **changes, "updated_by": "user", "updated_at": now_iso()}
        next_nodes.append(updated)

    if updated is None:
        raise ValueError("Node not found")

    await _write_graph(db, project_id, user_id, nodes=next_nodes, edges=project.get("rationale_edges", []))
    return updated


async def delete_graph_node(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    node_id: str,
) -> dict[str, Any] | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    nodes = [n for n in project.get("rationale_nodes", []) if n.get("node_id") != node_id]
    edges = [
        e
        for e in project.get("rationale_edges", [])
        if e.get("from_node_id") != node_id and e.get("to_node_id") != node_id
    ]
    queue = [item for item in project.get("negotiation_queue", []) if item != node_id]
    await _write_graph(
        db,
        project_id,
        user_id,
        nodes=nodes,
        edges=edges,
        negotiation_queue=queue,
    )
    return await get_project(db, project_id, user_id)


async def create_graph_edge(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    from_node_id: str,
    to_node_id: str,
    relation_type: str = "responds_to",
) -> dict[str, Any] | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    nodes_by_id = {n.get("node_id"): n for n in project.get("rationale_nodes", []) if n.get("node_id")}
    from_node = nodes_by_id.get(from_node_id)
    to_node = nodes_by_id.get(to_node_id)
    if from_node is None or to_node is None:
        raise ValueError("Node not found")
    validate_ibis_edge(from_node, to_node, relation_type)

    edge = build_rationale_edge(
        project_id=project_id,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        relation_type=relation_type,
        created_by="user",
    )
    edges = [*project.get("rationale_edges", []), edge]
    await _write_graph(db, project_id, user_id, nodes=project.get("rationale_nodes", []), edges=edges)
    return edge


async def delete_graph_edge(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    edge_id: str,
) -> dict[str, Any] | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    edges = [e for e in project.get("rationale_edges", []) if e.get("edge_id") != edge_id]
    await _write_graph(db, project_id, user_id, nodes=project.get("rationale_nodes", []), edges=edges)
    return await get_project(db, project_id, user_id)


async def toggle_negotiation_queue(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    node_id: str,
    *,
    in_queue: bool,
) -> dict[str, Any] | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    node = next((n for n in project.get("rationale_nodes", []) if n.get("node_id") == node_id), None)
    if node is None:
        raise ValueError("Node not found")
    if node.get("node_type") != "issue":
        raise ValueError("Only Issue nodes can join the negotiation queue")

    queue = list(project.get("negotiation_queue", []))
    if in_queue and node_id not in queue:
        queue.append(node_id)
    if not in_queue and node_id in queue:
        queue.remove(node_id)

    nodes = []
    for item in project.get("rationale_nodes", []):
        if item.get("node_id") != node_id:
            nodes.append(item)
            continue
        status = "needs_negotiation" if in_queue else "open"
        if not in_queue and item.get("status") == "needs_negotiation":
            status = "open"
        nodes.append(
            {
                **item,
                "in_negotiation_queue": in_queue,
                "status": status,
                "updated_by": "user",
                "updated_at": now_iso(),
            }
        )

    await _write_graph(
        db,
        project_id,
        user_id,
        nodes=nodes,
        edges=project.get("rationale_edges", []),
        negotiation_queue=queue,
    )
    return await get_project(db, project_id, user_id)


async def merge_coordinator_graph(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    proposed_nodes: list[dict[str, Any]],
    proposed_edges: list[dict[str, Any]],
) -> tuple[list[str], dict[str, Any] | None]:
    from app.models.rationale_ops import merge_proposed_graph

    project = await get_project(db, project_id, user_id)
    if project is None:
        return [], None

    user_node_ids = {n["node_id"] for n in project.get("rationale_nodes", []) if n.get("created_by") == "user"}
    safe_nodes = [n for n in proposed_nodes if n.get("node_id") not in user_node_ids]
    nodes, edges = merge_proposed_graph(
        project_id=project_id,
        existing_nodes=project.get("rationale_nodes", []),
        existing_edges=project.get("rationale_edges", []),
        proposed_nodes=safe_nodes,
        proposed_edges=proposed_edges,
    )
    new_ids = [n["node_id"] for n in safe_nodes if n.get("node_id")]
    await _write_graph(db, project_id, user_id, nodes=nodes, edges=edges, mark_stale=False)
    updated = await get_project(db, project_id, user_id)
    return new_ids, updated


async def _write_graph(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    nodes: list[dict],
    edges: list[dict],
    negotiation_queue: list[str] | None = None,
    mark_stale: bool = True,
) -> None:
    update: dict[str, Any] = {
        "rationale_nodes": nodes,
        "rationale_edges": edges,
        "updated_at": now_iso(),
    }
    if negotiation_queue is not None:
        update["negotiation_queue"] = negotiation_queue
    if mark_stale:
        update.update(stale_set_fields({"modification_schemes": "stale_graph_changed"}))
    await db.projects.update_one({"_id": project_id, "user_id": user_id}, {"$set": update})
