from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import now_iso
from app.repositories.projects import get_project
from app.repositories.script_snapshots import snapshot_before_map_update
from app.services.agent_orchestrator import merge_pipeline_into_project_graph, run_coordinator_pipeline
from app.services.pipeline_log import log_step


async def sync_graph_from_script(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    changed_row_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Re-run Brand / Audience / Expert analysis after script edits and merge into IBIS graph."""
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    row_ids = {row_id for row_id in (changed_row_ids or []) if row_id}
    perspectives = {"brand", "expert"}
    if project.get("active_persona_id"):
        perspectives.add("audience")

    log_step(
        "graph_sync.from_script",
        phase="IN",
        project_id=project_id,
        changed_row_ids=sorted(row_ids),
        perspectives=sorted(perspectives),
    )

    await snapshot_before_map_update(db, project_id, user_id)

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"stale.rationale_graph": "generating", "updated_at": now_iso()}},
    )

    try:
        pipeline = await run_coordinator_pipeline(
            project,
            perspectives=perspectives,
            user_message=(
                "脚本已更新。请基于当前脚本内容补充或更新 IBIS 节点（Issue / Position / Argument），"
                "关联相关分镜行；不要生成修改方案（ModificationScheme）。"
            ),
            quotes=[],
            changed_row_ids=row_ids,
        )

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
        "node_updates": len(pipeline.node_updates),
        "assistant_reply": pipeline.assistant_reply,
    }
    log_step(
        "graph_sync.from_script",
        phase="OUT",
        project_id=project_id,
        nodes_added=result["nodes_added"],
    )
    return result
