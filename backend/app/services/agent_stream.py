from collections.abc import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.agent_messages import create_agent_message, list_agent_messages
from app.repositories.projects import get_project
from app.services.agent_context import build_agent_chat_messages, build_prompt_variables
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
    try:
        async for token in LLMClient().stream_chat(
            messages=llm_messages,
            task_type=TASK_TYPES[agent_type],
            trace=trace,
        ):
            assistant_parts.append(token)
            yield encode_sse("token", {"content": token})
    except Exception as exc:
        yield encode_sse("error", {"message": str(exc)})
        return

    assistant_content = "".join(assistant_parts).strip()
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
    yield encode_sse("done", {"message_id": assistant["_id"]})
