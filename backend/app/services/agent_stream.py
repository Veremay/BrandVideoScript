from collections.abc import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.agent_messages import create_agent_message, list_agent_messages
from app.repositories.projects import (
    build_audience_analysis,
    create_brand_insight,
    get_project,
    save_audience_analysis,
)
from app.services.agent_context import (
    build_agent_chat_messages,
    build_prompt_variables,
    get_active_persona,
)
from app.services import audience_analysis_proposals as audience_marker
from app.services import brand_insight_proposals as brand_marker
from app.services.llm_client import LLMClient
from app.services.prompt_loader import PromptLoader
from app.services.sse import encode_sse
from app.services.trace import TraceRecorder


TASK_TYPES = {
    "brand": "brand_chat",
    "audience": "audience_chat",
    "expert": "expert_chat",
}

# Hold the longest possible literal marker prefix so partial artefact markers never
# reach the frontend before we can suppress them.
_HOLD_TAIL = max(brand_marker.MAX_MARKER_LEN, audience_marker.MAX_MARKER_LEN)


def _find_marker_start_for(agent_type: str, text: str) -> int:
    if agent_type == "brand":
        return brand_marker.find_marker_start(text)
    if agent_type == "audience":
        return audience_marker.find_marker_start(text)
    return -1


async def stream_agent_response(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    agent_type: str,
    content: str,
    quotes: list[dict],
) -> AsyncIterator[str]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        yield encode_sse("error", {"message": "Project not found"})
        return

    if agent_type not in TASK_TYPES:
        yield encode_sse("error", {"message": "Invalid agent type"})
        return

    if agent_type == "audience" and get_active_persona(project) is None:
        yield encode_sse(
            "error",
            {"message": "请先在观众 Agent 中创建并选择一个 persona，再发起对话。"},
        )
        return

    await create_agent_message(
        db,
        project_id=project_id,
        user_id=user_id,
        agent_type=agent_type,
        role="user",
        content=content,
        quotes=quotes,
    )
    recent_messages = await list_agent_messages(db, project_id=project_id, user_id=user_id, agent_type=agent_type, limit=20)
    variables = build_prompt_variables(project, recent_messages, quotes)

    try:
        system_prompt = PromptLoader().render(agent_type, variables)
    except Exception as exc:
        yield encode_sse("error", {"message": str(exc)})
        return

    llm_messages = build_agent_chat_messages(
        agent_type=agent_type,
        system_prompt=system_prompt,
        project=project,
        recent_messages=recent_messages[:-1],
        user_message=content,
        quotes=quotes,
    )

    trace = TraceRecorder(source=f"agent_stream:{agent_type}")
    assistant_parts: list[str] = []
    emitted_chars = 0

    try:
        async for token in LLMClient().stream_chat(
            messages=llm_messages,
            task_type=TASK_TYPES[agent_type],
            trace=trace,
        ):
            assistant_parts.append(token)
            full = "".join(assistant_parts)
            marker_idx = _find_marker_start_for(agent_type, full)
            if marker_idx >= 0:
                safe_end = marker_idx
            else:
                safe_end = max(emitted_chars, len(full) - _HOLD_TAIL)
            if safe_end > emitted_chars:
                chunk = full[emitted_chars:safe_end]
                if chunk:
                    yield encode_sse("token", {"content": chunk})
                    emitted_chars = safe_end
    except Exception as exc:
        yield encode_sse("error", {"message": str(exc)})
        return

    full = "".join(assistant_parts)
    marker_idx = _find_marker_start_for(agent_type, full)
    visible_end = marker_idx if marker_idx >= 0 else len(full)
    remaining = full[emitted_chars:visible_end]
    if remaining:
        yield encode_sse("token", {"content": remaining})

    done_payload: dict[str, object] = {"proposal_count": 0, "persisted_count": 0}

    if agent_type == "brand":
        proposals = brand_marker.parse_proposal_items(full) if marker_idx >= 0 else []
        assistant_content = (
            brand_marker.strip_proposal_block(full).strip() if marker_idx >= 0 else full.strip()
        )

        persisted_count = 0
        if proposals:
            for proposal in proposals:
                try:
                    await create_brand_insight(
                        db,
                        project_id,
                        user_id,
                        category=proposal["category"],
                        title=proposal["title"],
                        content=proposal["content"],
                        reason=proposal.get("reason", ""),
                        evidence=proposal.get("evidence", []),
                        confidence=proposal.get("confidence", "medium"),
                        status="new",
                        created_by="agent",
                    )
                    persisted_count += 1
                except ValueError:
                    continue

            yield encode_sse(
                "artifact",
                {
                    "type": "brand_insight_proposals",
                    "items": proposals,
                    "persisted_count": persisted_count,
                    "trace_run_id": trace.run_id,
                },
            )
        done_payload["proposal_count"] = len(proposals)
        done_payload["persisted_count"] = persisted_count

    elif agent_type == "audience":
        allowed_row_ids = {
            row.get("row_id")
            for row in (project.get("current_script", {}) or {}).get("rows", [])
            if isinstance(row.get("row_id"), str)
        }
        analysis_payload = (
            audience_marker.parse_analysis_payload(full, allowed_row_ids=allowed_row_ids)
            if marker_idx >= 0
            else None
        )
        assistant_content = (
            audience_marker.strip_proposal_block(full).strip() if marker_idx >= 0 else full.strip()
        )

        analysis_persisted = False
        persona = get_active_persona(project)
        if analysis_payload is not None and persona is not None:
            analysis = build_audience_analysis(
                persona_id=str(persona.get("persona_id") or ""),
                persona_name=str(persona.get("name") or ""),
                summary=str(analysis_payload.get("summary") or ""),
                naturalness_score=analysis_payload.get("naturalness_score"),
                credibility_score=analysis_payload.get("credibility_score"),
                ad_sensitivity_score=analysis_payload.get("ad_sensitivity_score"),
                key_risks=analysis_payload.get("key_risks") or [],
                liked_parts=analysis_payload.get("liked_parts") or [],
                rejected_parts=analysis_payload.get("rejected_parts") or [],
                suggestions=analysis_payload.get("suggestions") or [],
                based_on_script_updated_at=(project.get("current_script", {}) or {}).get("updated_at"),
            )
            await save_audience_analysis(db, project_id, user_id, analysis)
            analysis_persisted = True

            yield encode_sse(
                "artifact",
                {
                    "type": "audience_analysis",
                    "analysis": analysis,
                    "persona_id": persona.get("persona_id"),
                    "persona_name": persona.get("name"),
                    "persisted": True,
                    "trace_run_id": trace.run_id,
                },
            )
        done_payload["analysis_persisted"] = analysis_persisted

    else:
        assistant_content = full.strip()

    if not assistant_content:
        yield encode_sse("error", {"message": "Assistant response was empty"})
        return

    assistant = await create_agent_message(
        db,
        project_id=project_id,
        user_id=user_id,
        agent_type=agent_type,
        role="assistant",
        content=assistant_content,
        quotes=[],
    )
    done_payload["message_id"] = assistant["_id"]
    yield encode_sse("done", done_payload)
