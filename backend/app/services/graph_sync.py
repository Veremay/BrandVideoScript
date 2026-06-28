from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import now_iso
from app.repositories.projects import get_project
from app.repositories.script_snapshots import snapshot_before_map_update
from app.services.agent_orchestrator import (
    MAP_UPDATE_REPLACE_SOURCES,
    discard_non_conflicting_pipeline_positions,
    merge_pipeline_into_project_graph,
    reconcile_pipeline_into_project_graph,
    run_issue_population_pipeline,
    run_map_update_pipeline,
    run_reconcile_pipeline,
)
from app.services.pipeline_log import log_step


async def sync_graph_from_script(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    changed_row_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Re-analyze script on Update Map: fresh positions/issues, then reconcile existing issues."""
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    row_ids = {row_id for row_id in (changed_row_ids or []) if row_id}

    log_step(
        "graph_sync.from_script",
        phase="IN",
        project_id=project_id,
        changed_row_ids=sorted(row_ids),
    )

    await snapshot_before_map_update(db, project_id, user_id)

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"stale.rationale_graph": "generating", "updated_at": now_iso()}},
    )

    has_agent_nodes = any(
        n.get("created_by") == "agent" for n in project.get("rationale_nodes", [])
    )

    try:
        # Always re-run Brand + Audience on the script, then detect new conflicts.
        map_pipeline = await run_map_update_pipeline(project, changed_row_ids=row_ids)
        replace_sources = MAP_UPDATE_REPLACE_SOURCES if has_agent_nodes else None
        nodes, edges, _ = merge_pipeline_into_project_graph(
            project,
            map_pipeline,
            replace_agent_sources=replace_sources,
        )
        nodes, edges = discard_non_conflicting_pipeline_positions(nodes, edges, map_pipeline)
        pipeline = map_pipeline
        node_modifications: list[dict[str, Any]] = []
        issue_reviews: list[dict[str, Any]] = []

        if has_agent_nodes:
            interim = {
                **project,
                "rationale_nodes": nodes,
                "rationale_edges": edges,
            }
            reconcile_pipeline = await run_reconcile_pipeline(
                interim,
                user_message="脚本已更新。请重新评估每个冲突 issue 是否仍成立，并识别新冲突。",
                changed_row_ids=row_ids,
            )
            nodes, edges = reconcile_pipeline_into_project_graph(interim, reconcile_pipeline)
            node_modifications = reconcile_pipeline.node_modifications
            issue_reviews = reconcile_pipeline.issue_reviews
            if reconcile_pipeline.assistant_reply:
                pipeline.assistant_reply = reconcile_pipeline.assistant_reply

        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "rationale_nodes": nodes,
                    "rationale_edges": edges,
                    "updated_at": now_iso(),
                    "stale.rationale_graph": "up_to_date",
                    "stale.modification_schemes": "stale_graph_changed",
                }
            },
        )
    except Exception:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"stale.rationale_graph": "failed", "updated_at": now_iso()}},
        )
        raise

    updated = await get_project(db, project_id, user_id)
    result = {
        "project": updated,
        "nodes_added": len(pipeline.proposed_nodes),
        "node_updates": len(node_modifications),
        "issue_reviews": len(issue_reviews),
        "assistant_reply": pipeline.assistant_reply,
    }
    log_step(
        "graph_sync.from_script",
        phase="OUT",
        project_id=project_id,
        nodes_added=result["nodes_added"],
    )
    return result


async def populate_issue_with_positions(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    issue_id: str,
) -> dict[str, Any]:
    """Organize ≥2 conflicting Positions around a freshly created Issue and update the map."""
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    issue = next(
        (n for n in project.get("rationale_nodes", []) if n.get("node_id") == issue_id),
        None,
    )
    if issue is None or issue.get("node_type") != "issue":
        raise ValueError("Issue node not found")

    log_step("graph_sync.populate_issue", phase="IN", project_id=project_id, issue_id=issue_id)
    await snapshot_before_map_update(db, project_id, user_id)
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"stale.rationale_graph": "generating", "updated_at": now_iso()}},
    )

    try:
        pipeline = await run_issue_population_pipeline(project, issue_id)
        nodes, edges, safe_nodes = merge_pipeline_into_project_graph(project, pipeline)
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "rationale_nodes": nodes,
                    "rationale_edges": edges,
                    "updated_at": now_iso(),
                    "stale.rationale_graph": "up_to_date",
                    "stale.modification_schemes": "stale_graph_changed",
                }
            },
        )
    except Exception:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"stale.rationale_graph": "failed", "updated_at": now_iso()}},
        )
        raise

    updated = await get_project(db, project_id, user_id)
    result = {
        "project": updated,
        "nodes_added": len(safe_nodes),
        "assistant_reply": pipeline.assistant_reply,
    }
    log_step(
        "graph_sync.populate_issue",
        phase="OUT",
        project_id=project_id,
        issue_id=issue_id,
        nodes_added=result["nodes_added"],
    )
    return result
