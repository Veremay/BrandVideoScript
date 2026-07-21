from __future__ import annotations

from collections.abc import AsyncIterator
from html import escape
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.models.script import now_iso
from app.repositories.coordinator_messages import (
    build_coordinator_message,
    list_coordinator_messages,
    save_coordinator_message,
)
from app.repositories.modification_schemes import generate_modification_schemes
from app.repositories.projects import get_project
from app.repositories.script_snapshots import snapshot_before_map_update
from app.services.agent_llm import format_script_for_prompt
from app.services.agent_orchestrator import merge_pipeline_into_project_graph, run_coordinator_pipeline
from app.services.context_compress import maybe_compress_history
from app.services.coordinator_intent import wants_generate_modification_schemes
from app.services.llm_errors import LLMInvocationError
from app.services.llm_client import LLMClient
from app.services.pipeline_log import log_step
from app.services.prompt_loader import load_prompt
from app.services.sse import encode_sse


VANILLA_HISTORY_LIMIT = 80


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
    attachments: list[dict[str, Any]] | None = None,
    target_node_ids: list[str] | None = None,
    changed_row_ids: list[str] | None = None,
    mode: str = "full",
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
        attachments=[{"filename": item.get("filename"), "mime_type": item.get("mime_type"), "size": item.get("size")} for item in (attachments or [])],
        target_node_ids=target_node_ids,
        changed_row_ids=changed_row_ids,
        mode=mode,
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
        attachments=attachments or [],
        related_node_ids=target_node_ids or [],
    )
    await save_coordinator_message(db, user_doc)

    if mode == "vanilla":
        async for frame in _stream_vanilla_chat(
            db,
            project_id,
            user_id,
            project=project,
            message=message,
            task_type=task_type,
            requested_perspectives=list(perspectives),
            quotes=quotes or [],
        ):
            yield frame
        return

    if wants_generate_modification_schemes(message, task_type=task_type):
        async for frame in _stream_generate_modification_schemes(
            db,
            project_id,
            user_id,
            project=project,
            message=message,
            task_type=task_type,
            requested_perspectives=list(perspectives),
            quotes=quotes or [],
            target_node_ids=target_node_ids or [],
        ):
            yield frame
        return

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
        await snapshot_before_map_update(db, project_id, user_id)
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


def build_vanilla_system_content(project: dict) -> str:
    """System prompt + full current script (never compressed)."""
    system = load_prompt("vanilla_system.md")
    script_block = format_script_for_prompt(project)
    heading = "Full current script" if get_settings().prompt_language == "en" else "当前完整脚本"
    setup_data = project.get("vanilla_setup_data") or {}
    requirements = str(setup_data.get("brand_requirements") or "").strip()
    conflicts = str(setup_data.get("conflicts") or "").strip()
    requirements_block = (
        f"\n\n## Brand requirements provided by the creator\n{requirements}"
        if requirements
        else ""
    )
    conflicts_block = (
        f"\n\n## Conflicts and trade-offs identified by the creator\n{conflicts}"
        if conflicts
        else ""
    )
    persona_block = _format_vanilla_persona_block(project)
    return f"{system}{requirements_block}{persona_block}{conflicts_block}\n\n## {heading}\n{script_block}"


def _format_vanilla_persona_block(project: dict) -> str:
    active_id = project.get("active_persona_id")
    personas = project.get("personas") or []
    active = None
    if active_id:
        for persona in personas:
            if isinstance(persona, dict) and persona.get("persona_id") == active_id:
                active = persona
                break
    if active is None and len(personas) == 1 and isinstance(personas[0], dict):
        active = personas[0]
    if not isinstance(active, dict):
        return ""

    name = str(active.get("name") or "").strip()
    job = str(active.get("job") or "").strip()
    explanation = str(active.get("explanation") or "").strip()
    reason = str(active.get("reason") or "").strip()
    experiences = [
        str(item).strip()
        for item in (active.get("personal_experiences") or [])
        if str(item).strip()
    ][:10]
    characteristics = active.get("characteristic_values") or {}
    char_lines = []
    if isinstance(characteristics, dict):
        for key, value in list(characteristics.items())[:12]:
            label = str(key).strip()
            text = str(value).strip()
            if label and text:
                char_lines.append(f"- {label}: {text}")

    lines = ["\n\n## Active audience persona"]
    if name:
        lines.append(f"- Name: {name}")
    if job:
        lines.append(f"- Job / role: {job}")
    if explanation:
        lines.append(f"- Profile: {explanation}")
    if reason:
        lines.append(f"- Why they watch: {reason}")
    if experiences:
        lines.append("- Personal experiences:")
        lines.extend(f"  - {item}" for item in experiences)
    if char_lines:
        lines.append("- Characteristics:")
        lines.extend(f"  {item}" for item in char_lines)
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def _vanilla_message_content(doc: dict[str, Any]) -> str:
    content = str(doc.get("content") or "").strip()
    attachment_blocks: list[str] = []
    for attachment in doc.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        filename = escape(str(attachment.get("filename") or "attachment").strip(), quote=True)
        attachment_content = str(attachment.get("content") or "").strip()
        if not attachment_content:
            continue
        attachment_blocks.append(
            f'<attached_file name="{filename}">\n{attachment_content}\n</attached_file>'
        )
    if not attachment_blocks:
        return content
    return "\n\n".join([content, *attachment_blocks]).strip()


async def _stream_vanilla_chat(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    project: dict,
    message: str,
    task_type: str,
    requested_perspectives: list[str],
    quotes: list[dict],
) -> AsyncIterator[str]:
    """Plain single-LLM chat — system + full script + (compressed) history; no multi-agent pipeline."""
    log_step("coordinator_stream.vanilla", phase="IN", project_id=project_id, message=message)

    history = await list_coordinator_messages(db, project_id, user_id, limit=VANILLA_HISTORY_LIMIT)
    history_messages: list[dict[str, str]] = []
    for doc in history:
        role = doc.get("role")
        content = _vanilla_message_content(doc)
        if role in {"user", "assistant"} and content:
            history_messages.append({"role": role, "content": content})

    quote_text = "\n".join(str(q.get("text", "")).strip() for q in quotes if q.get("text"))
    if quote_text and history_messages and history_messages[-1]["role"] == "user":
        history_messages[-1]["content"] = (
            f"引用脚本片段：\n{quote_text}\n\n{history_messages[-1]['content']}"
        )

    llm = LLMClient()
    if not llm.settings.siliconflow_api_key:
        log_step("coordinator_stream.vanilla", phase="OUT", project_id=project_id, error="missing_api_key")
        yield encode_sse(
            "error",
            {"message": "未配置 LLM API key，无法调用模型。请在后端 .env 设置 SILICONFLOW_API_KEY 后重试。"},
        )
        return

    compressed_history = await maybe_compress_history(history_messages, llm=llm)
    llm_messages: list[dict[str, str]] = [
        {"role": "system", "content": build_vanilla_system_content(project)},
        *compressed_history,
    ]

    content_parts: list[str] = []
    # mock=False: vanilla never falls back to a canned reply — real model only.
    async for token in llm.stream_tokens(messages=llm_messages, task_type="vanilla_chat", mock=False):
        content_parts.append(token)
        yield encode_sse("token", {"content": token})
    reply = "".join(content_parts)
    log_step("coordinator_stream.vanilla", phase="OUT", project_id=project_id, reply=reply)

    assistant_doc = build_coordinator_message(
        project_id=project_id,
        user_id=user_id,
        role="assistant",
        content=reply,
        task_type=task_type,
        requested_perspectives=requested_perspectives,
        active_persona_id=project.get("active_persona_id"),
        quotes=quotes,
        related_node_ids=[],
        generated_artifact_ids=[],
    )
    await save_coordinator_message(db, assistant_doc)

    yield encode_sse(
        "done",
        {"message_id": assistant_doc["message_id"], "generated_artifact_ids": []},
    )


async def _stream_generate_modification_schemes(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    project: dict,
    message: str,
    task_type: str,
    requested_perspectives: list[str],
    quotes: list[dict],
    target_node_ids: list[str],
) -> AsyncIterator[str]:
    log_step(
        "coordinator_stream.generate_schemes",
        phase="IN",
        project_id=project_id,
        message=message,
    )

    position_targets = [node_id for node_id in target_node_ids if node_id]
    if not position_targets:
        position_targets = list(project.get("consideration_queue") or [])

    try:
        result = await generate_modification_schemes(
            db,
            project_id,
            user_id,
            target_position_ids=position_targets or None,
            user_message=message,
        )
    except LLMInvocationError as exc:
        updated = await get_project(db, project_id, user_id)
        yield encode_sse(
            "error",
            {
                "message": str(exc),
                "retryable": True,
                "project": updated,
            },
        )
        return
    except ValueError as exc:
        yield encode_sse("error", {"message": str(exc)})
        return

    updated_project = result.get("project") or {}
    new_schemes = result.get("schemes") or []
    all_schemes = updated_project.get("modification_schemes") or []
    scheme_ids = [s.get("scheme_id") for s in new_schemes if s.get("scheme_id")]

    yield encode_sse(
        "artifact",
        {
            "modification_schemes": all_schemes,
            "new_scheme_ids": scheme_ids,
        },
    )

    reply = result.get("assistant_reply") or (
        f"已生成脚本修改方案（非节点图）。请在 Revision Proposals / Script Editor 中预览 diff，"
        f"对每处修改选择接受或拒绝，可只写入部分修改。"
    )
    for index in range(0, len(reply), 12):
        yield encode_sse("token", {"content": reply[index : index + 12]})

    assistant_doc = build_coordinator_message(
        project_id=project_id,
        user_id=user_id,
        role="assistant",
        content=reply,
        task_type=task_type,
        requested_perspectives=requested_perspectives,
        active_persona_id=project.get("active_persona_id"),
        quotes=quotes,
        related_node_ids=position_targets,
        generated_artifact_ids=scheme_ids,
    )
    await save_coordinator_message(db, assistant_doc)

    done_payload = {
        "message_id": assistant_doc["message_id"],
        "generated_artifact_ids": scheme_ids,
        "scheme_count": len(new_schemes),
        "open_revision_proposals": True,
    }
    log_step(
        "coordinator_stream.generate_schemes",
        phase="OUT",
        project_id=project_id,
        scheme_count=len(new_schemes),
    )
    yield encode_sse("done", done_payload)
