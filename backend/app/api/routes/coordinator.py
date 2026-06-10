from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import (
    CoordinatorMessageListResponse,
    CoordinatorStreamRequest,
    GraphEdgeCreateRequest,
    GraphLayoutsBatchUpdateRequest,
    GraphNodeCreateRequest,
    GraphNodeConsiderationRequest,
    GraphNodeUpdateRequest,
    GraphSyncFromScriptRequest,
    GraphSyncFromScriptResponse,
    ProjectResponse,
)
from app.repositories.coordinator_messages import list_coordinator_messages
from app.repositories.graph import (
    batch_update_graph_layouts,
    create_graph_edge,
    create_graph_node,
    delete_graph_edge,
    delete_graph_node,
    toggle_consideration_queue,
    update_graph_node,
)
from app.repositories.projects import get_project
from app.services.coordinator_stream import stream_coordinator_chat
from app.services.graph_sync import sync_graph_from_script

router = APIRouter(prefix="/projects/{project_id}", tags=["coordinator"])


@router.post("/coordinator/stream")
async def coordinator_stream(
    project_id: str,
    payload: CoordinatorStreamRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> StreamingResponse:
    project = await get_project(db, project_id, payload.user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    async def event_generator():
        async for frame in stream_coordinator_chat(
            db,
            project_id,
            payload.user_id.strip(),
            message=payload.message,
            task_type=payload.task_type,
            requested_perspectives=payload.requested_perspectives,
            quotes=[q.model_dump() for q in payload.quotes],
            target_node_ids=payload.target_node_ids,
            changed_row_ids=payload.changed_row_ids,
        ):
            yield frame

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/coordinator/messages", response_model=CoordinatorMessageListResponse)
async def coordinator_messages(
    project_id: str,
    user_id: str = Query(min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    messages = await list_coordinator_messages(db, project_id, user_id.strip(), limit=limit)
    return {"messages": messages}


graph_router = APIRouter(prefix="/projects/{project_id}/graph", tags=["graph"])


@graph_router.post("/nodes", response_model=ProjectResponse, status_code=201)
async def add_graph_node(
    project_id: str,
    payload: GraphNodeCreateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        node = await create_graph_node(
            db,
            project_id,
            payload.user_id.strip(),
            node_type=payload.node_type,
            title=payload.title,
            content=payload.content,
            source_type=payload.source_type,
            source_perspective=payload.source_perspective,
            layout=payload.layout,
            status=payload.status,
            linked_script_refs=[ref.model_dump() for ref in payload.linked_script_refs],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if node is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project = await get_project(db, project_id, payload.user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@graph_router.patch("/layouts", response_model=ProjectResponse)
async def batch_update_layouts(
    project_id: str,
    payload: GraphLayoutsBatchUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    layouts = {item.node_id: item.layout for item in payload.layouts}
    try:
        project = await batch_update_graph_layouts(
            db,
            project_id,
            payload.user_id.strip(),
            layouts,
            skip_snapshot=payload.skip_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@graph_router.patch("/nodes/{node_id}", response_model=ProjectResponse)
async def edit_graph_node(
    project_id: str,
    node_id: str,
    payload: GraphNodeUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    changes = payload.model_dump(exclude={"user_id"}, exclude_none=True)
    try:
        await update_graph_node(db, project_id, payload.user_id.strip(), node_id, changes)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc
    project = await get_project(db, project_id, payload.user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@graph_router.delete("/nodes/{node_id}", response_model=ProjectResponse)
async def remove_graph_node(
    project_id: str,
    node_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await delete_graph_node(db, project_id, user_id.strip(), node_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@graph_router.post("/edges", response_model=ProjectResponse, status_code=201)
async def add_graph_edge(
    project_id: str,
    payload: GraphEdgeCreateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        await create_graph_edge(
            db,
            project_id,
            payload.user_id.strip(),
            from_node_id=payload.from_node_id,
            to_node_id=payload.to_node_id,
            relation_type=payload.relation_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    project = await get_project(db, project_id, payload.user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@graph_router.delete("/edges/{edge_id}", response_model=ProjectResponse)
async def remove_graph_edge(
    project_id: str,
    edge_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await delete_graph_edge(db, project_id, user_id.strip(), edge_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@graph_router.post("/sync-from-script", response_model=GraphSyncFromScriptResponse)
async def sync_graph_from_script_route(
    project_id: str,
    payload: GraphSyncFromScriptRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        return await sync_graph_from_script(
            db,
            project_id,
            payload.user_id.strip(),
            changed_row_ids=payload.changed_row_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc


@graph_router.patch("/nodes/{node_id}/consideration-queue", response_model=ProjectResponse)
async def update_consideration_queue(
    project_id: str,
    node_id: str,
    payload: GraphNodeConsiderationRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await toggle_consideration_queue(
            db,
            project_id,
            payload.user_id.strip(),
            node_id,
            in_queue=payload.in_queue,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
