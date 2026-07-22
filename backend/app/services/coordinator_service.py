from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.artifact_stale import mark_brief_changed, mark_persona_changed, stale_set_fields
from app.models.script import now_iso
from app.repositories.modification_schemes import generate_modification_schemes
from app.repositories.projects import get_project
from app.services.sse import encode_sse
from app.repositories.script_snapshots import snapshot_before_map_update
from app.services.agent_orchestrator import (
    merge_pipeline_into_project_graph,
    run_audience_pipeline,
    run_brief_initial_pipeline,
    run_map_update_pipeline,
)
from app.services.graph_sync import sync_graph_from_script
from app.services.persona_analytics import PersonaAnalyticsContext, get_persona_analytics_provider
from app.services.pipeline_log import log_step

GRAPH_SYNC_HEARTBEAT_SECONDS = 3.0


async def run_brief_initial_parse(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    brief = project.get("brief") or {}
    if not str(brief.get("text") or "").strip():
        raise ValueError("Brief text is empty")

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"brief.parse_status": "parsing", "updated_at": now_iso()}},
    )

    try:
        pipeline = await run_brief_initial_pipeline(project)
        brand_result = pipeline.brand_result or {}

        # Merge agent insights with user-saved ones (never overwrite user edits).
        existing_insights = [
            insight for insight in project.get("brand_insights", []) if insight.get("created_by") != "agent"
        ]
        new_insights = [*existing_insights, *brand_result.get("brand_insights", [])]

        # Brief parse only saves requirements — IBIS graph is NOT touched here.
        brand_perspective = {
            k: v
            for k, v in brand_result.items()
            if k not in {"brand_insights", "proposed_nodes", "proposed_edges", "node_updates"}
        }

        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "brief.parse_status": "parsed",
                    "brand_perspective_result": brand_perspective,
                    "brand_insights": new_insights,
                    **stale_set_fields(mark_brief_changed()),
                    "updated_at": now_iso(),
                }
            },
        )
    except Exception as exc:
        log_step("brief.parse.failed", phase="OUT", project_id=project_id, error=str(exc))
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"brief.parse_status": "failed", "updated_at": now_iso()}},
        )
        raise

    updated = await get_project(db, project_id, user_id)
    insights = updated.get("brand_insights") or []
    explicit_count = sum(1 for i in insights if i.get("category") == "explicit_requirement")
    implicit_count = sum(1 for i in insights if i.get("category") == "implicit_requirement")
    return {
        "project": updated,
        "parse_summary": {
            "explicit_requirements": explicit_count,
            "implicit_requirements": implicit_count,
        },
    }


async def stream_brief_parse(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
) -> AsyncIterator[str]:
    """SSE generator for brief parsing. Yields status → heartbeats → done/error."""
    yield encode_sse("status", {"message": "Parsing…"})

    task: asyncio.Task[dict[str, Any]] = asyncio.create_task(
        run_brief_initial_parse(db, project_id, user_id)
    )
    # Send a heartbeat every 8 s so the connection stays alive during long LLM calls.
    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=8.0)
        except asyncio.TimeoutError:
            yield encode_sse("heartbeat", {})

    exc = task.exception()
    if exc is not None:
        yield encode_sse("error", {"message": str(exc)})
        return

    result = task.result()
    # Keep the final SSE payload small. Embedding the full project (brief text +
    # insights) can break chunked transfer on long parses; the client refetches.
    yield encode_sse("done", {
        "parse_summary": result.get("parse_summary", {}),
    })


async def stream_graph_sync(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    changed_row_ids: list[str] | None = None,
) -> AsyncIterator[str]:
    """SSE generator for Update Map. Reports progress via the progress queue."""
    progress_queue: asyncio.Queue = asyncio.Queue()

    task: asyncio.Task[dict[str, Any]] = asyncio.create_task(
        sync_graph_from_script(db, project_id, user_id, changed_row_ids=changed_row_ids, progress_queue=progress_queue)
    )

    step = 0
    total = 0
    yield encode_sse("progress", {"step": step, "total": 1, "message": "Starting map update…"})

    while not task.done():
        # Try to read a progress message (non-blocking)
        try:
            msg = await asyncio.wait_for(progress_queue.get(), timeout=0.2)
            if "total" in msg:
                total = msg["total"]
            elif "message" in msg:
                step += 1
                yield encode_sse("progress", {"step": step, "total": total if total > 0 else step + 2, "message": msg["message"]})
        except asyncio.TimeoutError:
            pass

        # Heartbeat / task completion check
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=GRAPH_SYNC_HEARTBEAT_SECONDS)
        except asyncio.TimeoutError:
            yield encode_sse("heartbeat", {})

    # Drain remaining progress messages
    while not progress_queue.empty():
        try:
            msg = progress_queue.get_nowait()
            if "message" in msg:
                step += 1
                yield encode_sse("progress", {"step": step, "total": total if total > 0 else step + 1, "message": msg["message"]})
        except asyncio.QueueEmpty:
            break

    exc = task.exception()
    if exc is not None:
        yield encode_sse("error", {"message": str(exc)})
        return

    result = task.result()
    yield encode_sse("done", {"project": result.get("project"), "nodes_added": result.get("nodes_added", 0)})


async def stream_generate_modification_schemes(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    target_issue_ids: list[str] | None = None,
    target_position_ids: list[str] | None = None,
    user_message: str | None = None,
) -> AsyncIterator[str]:
    """SSE generator for Generate Modification Plan. Reports progress via queue."""
    progress_queue: asyncio.Queue = asyncio.Queue()

    task: asyncio.Task[dict[str, Any]] = asyncio.create_task(
        generate_modification_schemes(
            db, project_id, user_id,
            target_issue_ids=target_issue_ids,
            target_position_ids=target_position_ids,
            user_message=user_message,
            progress_queue=progress_queue,
        )
    )

    step = 0
    total = 3  # prepare, generate, save
    yield encode_sse("progress", {"step": step, "total": total, "message": "Starting…"})

    while not task.done():
        try:
            msg = await asyncio.wait_for(progress_queue.get(), timeout=0.2)
            if "message" in msg:
                step += 1
                yield encode_sse("progress", {"step": step, "total": total, "message": msg["message"]})
        except asyncio.TimeoutError:
            pass

        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=GRAPH_SYNC_HEARTBEAT_SECONDS)
        except asyncio.TimeoutError:
            yield encode_sse("heartbeat", {})

    while not progress_queue.empty():
        try:
            msg = progress_queue.get_nowait()
            if "message" in msg:
                step += 1
                yield encode_sse("progress", {"step": step, "total": total, "message": msg["message"]})
        except asyncio.QueueEmpty:
            break

    exc = task.exception()
    if exc is not None:
        yield encode_sse("error", {"message": str(exc)})
        return

    result = task.result()
    done_payload = {
        "project": result.get("project"),
        "schemes": result.get("schemes") or [],
        "assistant_reply": result.get("assistant_reply", ""),
    }
    try:
        yield encode_sse("done", done_payload)
    except (TypeError, ValueError):
        # Full project/schemes payload can fail JSON encoding; client will refetch.
        yield encode_sse(
            "done",
            {
                "project": None,
                "schemes": [],
                "assistant_reply": str(result.get("assistant_reply", "")),
                "refetch": True,
            },
        )


async def run_persona_provisioned_parse(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")
    if not project.get("active_persona_id"):
        raise ValueError("Active persona is required")

    pipeline = await run_audience_pipeline(project)
    audience_sources = {"audience_persona", "audience_simulation"}
    nodes, edges, _ = merge_pipeline_into_project_graph(
        project,
        pipeline,
        replace_agent_sources=audience_sources,
    )

    audience_result = pipeline.audience_result or {}
    await snapshot_before_map_update(db, project_id, user_id)
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "audience_perspective_result": {
                    k: v
                    for k, v in audience_result.items()
                    if k not in {"proposed_nodes", "proposed_edges", "node_updates"}
                },
                "rationale_nodes": nodes,
                "rationale_edges": edges,
                "stale.rationale_graph": "up_to_date",
                "updated_at": now_iso(),
            }
        },
    )

    updated = await get_project(db, project_id, user_id)
    return {
        "project": updated,
        "parse_summary": {
            "audience_issues": len([n for n in nodes if str(n.get("source_type", "")).startswith("audience")]),
            "total_nodes": len(nodes),
        },
    }


async def provision_personas_from_analytics(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    platform_context: str,
    content_category: str | None = None,
    brand_name: str | None = None,
    video_topic: str | None = None,
    run_audience_parse: bool = True,
) -> dict[str, Any]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    provider = get_persona_analytics_provider()
    ctx = PersonaAnalyticsContext(
        project_id=project_id,
        platform_context=platform_context,  # type: ignore[arg-type]
        content_category=content_category,
        brand_name=brand_name,
        video_topic=video_topic,
    )
    personas = await provider.generate_personas(ctx)
    active_id = personas[0]["persona_id"] if personas else None

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "platform_context": platform_context,
                "personas": personas,
                "active_persona_id": active_id,
                "updated_at": now_iso(),
                **stale_set_fields(mark_persona_changed()),
            }
        },
    )

    parse_result: dict[str, Any] | None = None
    if run_audience_parse and active_id:
        parse_result = await run_persona_provisioned_parse(db, project_id, user_id)

    project_doc = await get_project(db, project_id, user_id)
    return {
        "personas": personas,
        "active_persona_id": active_id,
        "analytics_meta": personas[0].get("analytics_meta") if personas else None,
        "project": project_doc,
        "audience_parse": parse_result,
    }
