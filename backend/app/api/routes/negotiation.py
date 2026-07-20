from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import (
    CommunicationSupportToggleRequest,
    NegotiationGenerateRequest,
    NegotiationGenerateResponse,
    ProjectResponse,
    VanillaArguePromptRequest,
    VanillaArguePromptResponse,
)
from app.repositories.graph import toggle_communication_support
from app.repositories.negotiation import generate_negotiation_preparation
from app.repositories.projects import get_project
from app.services.negotiation_stream import stream_generate_negotiation
from app.services.vanilla_argue import (
    assert_feedback_column,
    build_vanilla_argue_append_block,
    build_vanilla_argue_prompt,
    feedback_cell_value,
    scene_number_for_row,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["negotiation"])


@router.patch("/communication-support", response_model=ProjectResponse)
async def update_communication_support(
    project_id: str,
    payload: CommunicationSupportToggleRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await toggle_communication_support(
            db,
            project_id,
            payload.user_id.strip(),
            row_id=payload.row_id,
            column_id=payload.column_id,
            in_list=payload.in_list,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/vanilla/argue-prompt", response_model=VanillaArguePromptResponse)
async def post_vanilla_argue_prompt(
    project_id: str,
    payload: VanillaArguePromptRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    """Fill a bilingual negotiation draft template for the vanilla chatbot input box.

    Does not modify the vanilla system prompt — only returns user-facing draft text.
    """
    project = await get_project(db, project_id, payload.user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    mode = project.get("mode") or (project.get("current_script") or {}).get("settings", {}).get("mode")
    if mode != "vanilla":
        raise HTTPException(status_code=400, detail="Argue prompt templates are only available in vanilla mode")

    script = project.get("current_script") or {}
    try:
        assert_feedback_column(script, payload.column_id)
        feedback = feedback_cell_value(script, payload.row_id, payload.column_id)
        scene_number = scene_number_for_row(script, payload.row_id)
        prompt = build_vanilla_argue_prompt(scene_number, feedback)
        append_block = build_vanilla_argue_append_block(scene_number, feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"prompt": prompt, "append_block": append_block}


@router.post("/negotiation/generate", response_model=NegotiationGenerateResponse)
async def post_generate_negotiation(
    project_id: str,
    payload: NegotiationGenerateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        return await generate_negotiation_preparation(
            db,
            project_id,
            payload.user_id.strip(),
            message=payload.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc


@router.post("/negotiation/generate/stream")
async def post_generate_negotiation_stream(
    project_id: str,
    payload: NegotiationGenerateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> StreamingResponse:
    return StreamingResponse(
        stream_generate_negotiation(
            db,
            project_id,
            payload.user_id.strip(),
            message=payload.message,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/negotiation", response_model=NegotiationGenerateResponse)
async def get_negotiation(
    project_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project": project,
        "negotiation_preparation": project.get("negotiation_preparation"),
        "assistant_reply": "",
    }
