from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import now_iso
from app.repositories.projects import get_project
from app.services.agents.expert_agent import run_expert_generate_negotiation_stream
from app.services.audit_log import (
    negotiation_preparation_slice,
    nodes_slice,
    record_mutation,
    script_slice,
)
from app.services.llm_errors import LLMInvocationError
from app.services.sse import encode_sse


async def stream_generate_negotiation(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    message: str | None = None,
) -> AsyncIterator[str]:
    """SSE generator for negotiation plan with incremental reply tokens."""
    project = await get_project(db, project_id, user_id)
    if project is None:
        yield encode_sse("error", {"message": "Project not found"})
        return

    before_prep = negotiation_preparation_slice(project.get("negotiation_preparation"))
    support_nodes = [
        node
        for node in (project.get("rationale_nodes") or [])
        if node.get("in_communication_support_queue")
        or node.get("node_id") in set(project.get("communication_support_queue") or [])
    ]
    considered_nodes = [
        node
        for node in (project.get("rationale_nodes") or [])
        if node.get("in_consideration_queue")
        or node.get("node_id") in set(project.get("consideration_queue") or [])
    ]

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"stale.negotiation_preparation": "generating", "updated_at": now_iso()}},
    )

    yield encode_sse("progress", {"message": "Generating negotiation plan…"})

    result: dict[str, Any] | None = None
    try:
        async for event in run_expert_generate_negotiation_stream(project, message=message):
            event_type = event.get("type")
            if event_type == "reply_token":
                yield encode_sse(
                    "reply_token",
                    {
                        "dispute_index": event.get("dispute_index", 0),
                        "content": event.get("content", ""),
                    },
                )
            elif event_type == "dispute_meta":
                yield encode_sse(
                    "dispute_meta",
                    {
                        "dispute_index": event.get("dispute_index", 0),
                        "issue_node_id": event.get("issue_node_id", ""),
                        "brand_feedback": event.get("brand_feedback", ""),
                    },
                )
            elif event_type == "dispute_ready":
                yield encode_sse(
                    "dispute_ready",
                    {
                        "dispute_index": event.get("dispute_index", 0),
                        "issue_node_id": event.get("issue_node_id", ""),
                        "brand_feedback": event.get("brand_feedback", ""),
                        "reply": event.get("reply", ""),
                    },
                )
            elif event_type == "result":
                result = event
    except LLMInvocationError as exc:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"stale.negotiation_preparation": "failed", "updated_at": now_iso()}},
        )
        yield encode_sse("error", {"message": str(exc)})
        return
    except Exception as exc:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"stale.negotiation_preparation": "failed", "updated_at": now_iso()}},
        )
        yield encode_sse("error", {"message": str(exc)})
        return

    if result is None:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"stale.negotiation_preparation": "failed", "updated_at": now_iso()}},
        )
        yield encode_sse("error", {"message": "Negotiation generation ended without a result"})
        return

    prep = result.get("negotiation_preparation")
    try:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "negotiation_preparation": prep,
                    "stale.negotiation_preparation": "up_to_date",
                    "updated_at": now_iso(),
                }
            },
        )
    except Exception as exc:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"stale.negotiation_preparation": "failed", "updated_at": now_iso()}},
        )
        yield encode_sse("error", {"message": str(exc)})
        return

    updated = await get_project(db, project_id, user_id)
    await record_mutation(
        db,
        action="negotiation.generate",
        user_id=user_id,
        project_id=project_id,
        before={
            "negotiation_preparation": before_prep,
            "script": script_slice(project.get("current_script")),
            "support_nodes": nodes_slice(support_nodes),
            "considered_nodes": nodes_slice(considered_nodes),
        },
        after={
            "negotiation_preparation": negotiation_preparation_slice(prep if isinstance(prep, dict) else None),
            "script": script_slice(updated.get("current_script") if updated else None),
            "support_nodes": nodes_slice(support_nodes),
            "considered_nodes": nodes_slice(considered_nodes),
        },
        meta={"message": (message or "")[:500], "stream": True},
    )

    yield encode_sse(
        "done",
        {
            "project": updated,
            "negotiation_preparation": prep,
            "assistant_reply": result.get("assistant_reply", ""),
        },
    )
