from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import now_iso
from app.repositories.coordinator_messages import build_coordinator_message, save_coordinator_message
from app.repositories.projects import get_project
from app.services.agent_orchestrator import merge_pipeline_into_project_graph, run_coordinator_pipeline
from app.services.llm_client import LLMClient
from app.services.pipeline_log import log_step
from app.services.sse import encode_sse


def _resolve_perspectives(requested: list[str]) -> set[str]:
    if not requested or "comprehensive" in requested:
        return {"brand", "audience", "expert"}
    return {item for item in requested if item in {"brand", "audience", "expert"}}


async def stream_coordinator_chat(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    message: str,
    task_type: str = "user_message",
    requested_perspectives: list[str] | None = None,
    quotes: list[dict[str, Any]] | None = None,
    target_node_ids: list[str] | None = None,
    changed_row_ids: list[str] | None = None,
) -> AsyncIterator[str]:
    log_step(
        "coordinator_stream",
        phase="IN",
        project_id=project_id,
        user_id=user_id,
        message=message,
        task_type=task_type,
        requested_perspectives=requested_perspectives,
        quotes=quotes,
        target_node_ids=target_node_ids,
        changed_row_ids=changed_row_ids,
    )

    project = await get_project(db, project_id, user_id)
    if project is None:
        yield encode_sse("error", {"message": "Project not found"})
        return

    perspectives = _resolve_perspectives(requested_perspectives or [])
    row_ids = {row_id for row_id in (changed_row_ids or []) if row_id}
    if quotes and quotes[0].get("row_id"):
        row_ids.add(str(quotes[0]["row_id"]))

    user_doc = build_coordinator_message(
        project_id=project_id,
        user_id=user_id,
        role="user",
        content=message,
        task_type=task_type,
        requested_perspectives=list(perspectives),
        active_persona_id=project.get("active_persona_id"),
        quotes=quotes or [],
        related_node_ids=target_node_ids or [],
    )
    await save_coordinator_message(db, user_doc)

    pipeline = await run_coordinator_pipeline(
        project,
        perspectives=perspectives,
        user_message=message,
        quotes=quotes or [],
        changed_row_ids=row_ids,
    )

    nodes, edges, safe_nodes = merge_pipeline_into_project_graph(project, pipeline)
    related_node_ids = [n["node_id"] for n in safe_nodes if n.get("node_id")]

    log_step(
        "coordinator_stream.merge_graph",
        phase="OUT",
        project_id=project_id,
        safe_nodes=len(safe_nodes),
        graph_nodes=len(nodes),
        graph_edges=len(edges),
        assistant_reply_preview=(pipeline.assistant_reply or "")[:300],
    )

    if safe_nodes or pipeline.node_updates:
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
        yield encode_sse(
            "artifact",
            {
                "rationale_nodes": safe_nodes,
                "rationale_edges": pipeline.proposed_edges,
                "related_node_ids": related_node_ids,
                "node_updates": pipeline.node_updates,
            },
        )

    reply = pipeline.assistant_reply
    llm = LLMClient()
    if reply:
        log_step("coordinator_stream.reply", phase="OUT", source="expert_assistant_reply", reply=reply)
        for index in range(0, len(reply), 12):
            yield encode_sse("token", {"content": reply[index : index + 12]})
    elif llm.settings.siliconflow_api_key:
        log_step("coordinator_stream.reply", phase="IN", source="coordinator_chat_stream")
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Coordinator Agent. Summarize multi-agent IBIS analysis in clear Chinese. "
                    f"New nodes: {len(safe_nodes)}."
                ),
            },
            {"role": "user", "content": message},
        ]
        content_parts: list[str] = []
        async for token in llm.stream_tokens(messages=messages, task_type="coordinator_chat"):
            content_parts.append(token)
            yield encode_sse("token", {"content": token})
        reply = "".join(content_parts)
        log_step("coordinator_stream.reply", phase="OUT", source="coordinator_chat_stream", reply=reply)
    else:
        reply = "已调度 Brand / Audience / Expert 完成 IBIS 推理，请在 Node Graph 中查看。"
        log_step("coordinator_stream.reply", phase="OUT", source="fallback_no_key", reply=reply)
        yield encode_sse("token", {"content": reply})

    assistant_doc = build_coordinator_message(
        project_id=project_id,
        user_id=user_id,
        role="assistant",
        content=reply,
        task_type=task_type,
        requested_perspectives=list(perspectives),
        active_persona_id=project.get("active_persona_id"),
        quotes=quotes or [],
        related_node_ids=related_node_ids or (target_node_ids or []),
        generated_artifact_ids=related_node_ids,
    )
    await save_coordinator_message(db, assistant_doc)

    done_payload = {
        "message_id": assistant_doc["message_id"],
        "generated_artifact_ids": related_node_ids,
        "graph_node_count": len(nodes),
        "graph_edge_count": len(edges),
    }
    log_step("coordinator_stream", phase="OUT", project_id=project_id, done=done_payload)
    yield encode_sse("done", done_payload)
