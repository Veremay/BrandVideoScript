from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.artifact_stale import stale_set_fields
from app.models.choice_history import record_considered_position
from app.models.rationale_ops import (
    MAX_CONSIDERATION_QUEUE_SIZE,
    build_rationale_edge,
    build_rationale_node,
    collect_issue_delete_cascade,
    collect_position_delete_cascade,
    count_consideration_positions,
    drop_agent_issues_without_positions,
    validate_ibis_edge,
    validate_ibis_graph_integrity,
)
from app.models.script import now_iso
from app.repositories.projects import get_project
from app.repositories.script_snapshots import snapshot_before_map_update


def _build_carrier_issue_for_position(project_id: str, position: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    title = str(position.get("title") or "立场").strip()
    issue = build_rationale_node(
        project_id=project_id,
        node_type="issue",
        title=f"关于「{title[:40]}」的议题",
        content=f"承载立场：{title}",
        source_type=str(position.get("source_type") or "creator_manual"),
        source_perspective=str(position.get("source_perspective") or "creator"),
        created_by=str(position.get("created_by") or "user"),
        based_on_script_version_id=position.get("based_on_script_version_id"),
    )
    edge = build_rationale_edge(
        project_id=project_id,
        from_node_id=str(position["node_id"]),
        to_node_id=str(issue["node_id"]),
        relation_type="responds_to",
        created_by=str(position.get("created_by") or "user"),
    )
    return issue, edge


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
    edges = list(project.get("rationale_edges", []))
    if node_type == "position":
        issue, edge = _build_carrier_issue_for_position(project_id, node)
        nodes.append(issue)
        edges.append(edge)
    await _write_graph(db, project_id, user_id, nodes=nodes, edges=edges)
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

    nodes_by_id = {n.get("node_id"): n for n in project.get("rationale_nodes", []) if n.get("node_id")}
    target = nodes_by_id.get(node_id)
    if target is None:
        raise ValueError("Node not found")

    project_edges = project.get("rationale_edges", [])
    node_type = str(target.get("node_type"))
    if node_type == "issue":
        cascade_ids = collect_issue_delete_cascade(nodes_by_id, project_edges, node_id)
    elif node_type == "position":
        cascade_ids = collect_position_delete_cascade(nodes_by_id, project_edges, node_id)
    else:
        cascade_ids = {node_id}

    affected_issue_ids: set[str] = set()
    if node_type == "position":
        for edge in project_edges:
            if edge.get("from_node_id") not in cascade_ids or edge.get("relation_type") != "responds_to":
                continue
            issue_id = str(edge.get("to_node_id") or "")
            if issue_id and issue_id not in cascade_ids:
                affected_issue_ids.add(issue_id)

    nodes = [n for n in project.get("rationale_nodes", []) if n.get("node_id") not in cascade_ids]
    edges = [
        e
        for e in project_edges
        if e.get("from_node_id") not in cascade_ids and e.get("to_node_id") not in cascade_ids
    ]
    dropped_issue_ids: set[str] = set()
    if affected_issue_ids:
        nodes, edges, dropped_issue_ids = drop_agent_issues_without_positions(
            nodes, edges, affected_issue_ids
        )
        remaining_affected = affected_issue_ids - dropped_issue_ids
        if remaining_affected:
            validate_ibis_graph_integrity(
                nodes,
                edges,
                node_ids=remaining_affected,
                require_linked_for=lambda _node: True,
            )
    queue = [item for item in project.get("consideration_queue", []) if item not in cascade_ids]
    await _write_graph(
        db,
        project_id,
        user_id,
        nodes=nodes,
        edges=edges,
        consideration_queue=queue,
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

    removed = next((e for e in project.get("rationale_edges", []) if e.get("edge_id") == edge_id), None)
    if removed is None:
        raise ValueError("Edge not found")

    edges = [e for e in project.get("rationale_edges", []) if e.get("edge_id") != edge_id]
    nodes = list(project.get("rationale_nodes", []))
    affected: set[str] = set()
    relation = removed.get("relation_type")
    if relation == "responds_to":
        affected.add(str(removed.get("to_node_id") or ""))
    elif relation in {"supports", "opposes"}:
        affected.add(str(removed.get("from_node_id") or ""))
    dropped_issue_ids: set[str] = set()
    if affected:
        if relation == "responds_to":
            nodes, edges, dropped_issue_ids = drop_agent_issues_without_positions(nodes, edges, affected)
            remaining_affected = affected - dropped_issue_ids
            if remaining_affected:
                validate_ibis_graph_integrity(
                    nodes,
                    edges,
                    node_ids=remaining_affected,
                    require_linked_for=lambda _node: True,
                )
        else:
            # Manual Argument deletion may intentionally leave a Position without
            # arguments. Agent-generated graph merges still enforce completeness.
            pass
    await _write_graph(db, project_id, user_id, nodes=nodes, edges=edges)
    return await get_project(db, project_id, user_id)


async def toggle_consideration_queue(
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
        # The referenced Position may have been superseded/removed by a reconcile.
        # Allow cleaning up a stale queue entry; disallow adding a missing node.
        if in_queue:
            raise ValueError("Node not found")
        queue = [item for item in project.get("consideration_queue", []) if item != node_id]
        await _write_graph(
            db,
            project_id,
            user_id,
            nodes=project.get("rationale_nodes", []),
            edges=project.get("rationale_edges", []),
            consideration_queue=queue,
        )
        return await get_project(db, project_id, user_id)
    if node.get("node_type") != "position":
        raise ValueError("Only Position nodes can join the consideration queue")

    queue = list(project.get("consideration_queue", []))
    if in_queue and node_id not in queue:
        if count_consideration_positions(project) >= MAX_CONSIDERATION_QUEUE_SIZE:
            raise ValueError(
                f"TO BE CONSIDERED list can hold at most {MAX_CONSIDERATION_QUEUE_SIZE} positions"
            )
        queue.append(node_id)
    if not in_queue and node_id in queue:
        queue.remove(node_id)

    nodes = []
    for item in project.get("rationale_nodes", []):
        if item.get("node_id") != node_id:
            nodes.append(item)
            continue
        status = "to_be_considered" if in_queue else "open"
        if not in_queue and item.get("status") == "to_be_considered":
            status = "open"
        nodes.append(
            {
                **item,
                "in_consideration_queue": in_queue,
                "in_negotiation_queue": False,
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
        consideration_queue=queue,
        choice_history=record_considered_position(project.get("choice_history"), node) if in_queue else None,
    )
    return await get_project(db, project_id, user_id)


def _feedback_cell_value(script: dict[str, Any], row_id: str, column_id: str) -> str:
    for row in script.get("rows", []):
        if row.get("row_id") != row_id:
            continue
        for cell in row.get("cells", []):
            if cell.get("column_id") == column_id:
                return str(cell.get("value", "")).strip()
    return ""


def _find_feedback_node(nodes: list[dict[str, Any]], row_id: str) -> dict[str, Any] | None:
    for node in nodes:
        if node.get("source_type") != "brand_feedback" or node.get("node_type") != "position":
            continue
        for ref in node.get("linked_script_refs") or []:
            if ref.get("row_id") == row_id:
                return node
    return None


async def toggle_communication_support(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    row_id: str,
    column_id: str,
    in_list: bool,
) -> dict[str, Any] | None:
    """Add/remove a brand-feedback row from the creator's communication support list."""
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    script = project.get("current_script") or {}
    nodes = list(project.get("rationale_nodes") or [])
    queue = list(project.get("communication_support_queue") or [])
    existing = _find_feedback_node(nodes, row_id)

    if in_list:
        feedback_text = _feedback_cell_value(script, row_id, column_id)
        if not feedback_text:
            raise ValueError("This row has no brand feedback to argue")

        if row_id not in queue:
            queue.append(row_id)
    else:
        queue = [item for item in queue if item != row_id]
        if existing is not None:
            node_id = existing["node_id"]
            nodes = [
                {
                    **item,
                    "in_communication_support_queue": False,
                    "status": "open" if item.get("status") == "needs_negotiation" else item.get("status"),
                    "updated_by": "user",
                    "updated_at": now_iso(),
                }
                if item.get("node_id") == node_id
                else item
                for item in nodes
            ]
            queue = [item for item in queue if item != node_id]

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "rationale_nodes": nodes,
                "rationale_edges": project.get("rationale_edges", []),
                "communication_support_queue": queue,
                "updated_at": now_iso(),
                **stale_set_fields({"negotiation_preparation": "stale_brand_feedback"}),
            }
        },
    )
    return await get_project(db, project_id, user_id)


async def batch_update_graph_layouts(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    layouts: dict[str, dict[str, float]],
    *,
    skip_snapshot: bool = False,
) -> dict[str, Any] | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    if not layouts:
        return project

    if not skip_snapshot:
        await snapshot_before_map_update(db, project_id, user_id)

    layout_by_id = {node_id: layout for node_id, layout in layouts.items() if node_id}
    next_nodes: list[dict] = []
    for node in project.get("rationale_nodes", []):
        node_id = node.get("node_id")
        layout = layout_by_id.get(node_id)
        if layout is None:
            next_nodes.append(node)
            continue
        next_nodes.append(
            {
                **node,
                "layout": layout,
                "updated_by": "user",
                "updated_at": now_iso(),
            }
        )

    await _write_graph(
        db,
        project_id,
        user_id,
        nodes=next_nodes,
        edges=project.get("rationale_edges", []),
        snapshot_before=False,
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
    consideration_queue: list[str] | None = None,
    choice_history: dict[str, Any] | None = None,
    mark_stale: bool = True,
    snapshot_before: bool = True,
) -> None:
    if snapshot_before:
        await snapshot_before_map_update(db, project_id, user_id)

    update: dict[str, Any] = {
        "rationale_nodes": nodes,
        "rationale_edges": edges,
        "updated_at": now_iso(),
    }
    if consideration_queue is not None:
        update["consideration_queue"] = consideration_queue
    if choice_history is not None:
        update["choice_history"] = choice_history
    if mark_stale:
        update.update(stale_set_fields({"modification_schemes": "stale_graph_changed"}))
    await db.projects.update_one({"_id": project_id, "user_id": user_id}, {"$set": update})
