from collections.abc import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.agent_messages import create_agent_message, list_agent_messages
from app.repositories.projects import get_project
from app.services.agent_context import build_agent_chat_messages, build_prompt_variables
from app.repositories.projects import create_brand_insight
from app.services.brand_insight_proposals import (
    MAX_MARKER_LEN,
    find_marker_start,
    parse_proposal_items,
    strip_proposal_block,
)
from app.services.llm_client import LLMClient
from app.services.prompt_loader import PromptLoader
from app.services.sse import encode_sse
from app.services.trace import TraceRecorder


TASK_TYPES = {
    "brand": "brand_chat",
    "audience": "audience_chat",
    "expert": "expert_chat",
}


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
    # Hold back the longest possible marker prefix so partial markers never reach
    # the frontend before we can suppress them.
    hold_tail = MAX_MARKER_LEN

    try:
        async for token in LLMClient().stream_chat(
            messages=llm_messages,
            task_type=TASK_TYPES[agent_type],
            trace=trace,
        ):
            assistant_parts.append(token)
            full = "".join(assistant_parts)
            marker_idx = find_marker_start(full)
            if marker_idx >= 0:
                safe_end = marker_idx
            else:
                safe_end = max(emitted_chars, len(full) - hold_tail)
            if safe_end > emitted_chars:
                chunk = full[emitted_chars:safe_end]
                if chunk:
                    yield encode_sse("token", {"content": chunk})
                    emitted_chars = safe_end
    except Exception as exc:
        yield encode_sse("error", {"message": str(exc)})
        return

    full = "".join(assistant_parts)
    marker_idx = find_marker_start(full)
    visible_end = marker_idx if marker_idx >= 0 else len(full)
    remaining = full[emitted_chars:visible_end]
    if remaining:
        yield encode_sse("token", {"content": remaining})

    proposals = parse_proposal_items(full) if marker_idx >= 0 else []
    assistant_content = strip_proposal_block(full).strip() if marker_idx >= 0 else full.strip()

    persisted_count = 0
    if proposals and agent_type == "brand":
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
                # Skip malformed proposals; surfaced via artifact event for UI fallback.
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
    yield encode_sse(
        "done",
        {
            "message_id": assistant["_id"],
            "proposal_count": len(proposals),
            "persisted_count": persisted_count,
        },
    )
