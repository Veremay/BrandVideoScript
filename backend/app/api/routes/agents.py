from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import AgentMessagesResponse, AgentStreamRequest
from app.repositories.agent_messages import list_agent_messages
from app.repositories.projects import get_project
from app.services.agent_stream import stream_agent_response

router = APIRouter(prefix="/projects/{project_id}/agents", tags=["agents"])


@router.get("/{agent_type}/messages", response_model=AgentMessagesResponse)
async def get_agent_messages(
    project_id: str,
    agent_type: str,
    user_id: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"messages": await list_agent_messages(db, project_id=project_id, user_id=user_id, agent_type=agent_type, limit=limit)}


@router.post("/{agent_type}/stream")
async def stream_agent(
    project_id: str,
    agent_type: str,
    payload: AgentStreamRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> StreamingResponse:
    return StreamingResponse(
        stream_agent_response(
            db,
            project_id=project_id,
            user_id=payload.user_id.strip(),
            agent_type=agent_type,
            content=payload.content,
            quotes=[quote.model_dump(exclude_none=True) for quote in payload.quotes],
        ),
        media_type="text/event-stream",
    )
