from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import (
    CommunicationSupportToggleRequest,
    NegotiationGenerateRequest,
    NegotiationGenerateResponse,
    ProjectResponse,
)
from app.repositories.graph import toggle_communication_support
from app.repositories.negotiation import generate_negotiation_preparation
from app.repositories.projects import get_project

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
