from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import (
    ModificationSchemeApplyRequest,
    ModificationSchemeApplyResponse,
    ModificationSchemeGenerateRequest,
    ModificationSchemeGenerateResponse,
    ModificationSchemeListResponse,
)
from app.repositories.modification_schemes import (
    apply_modification_scheme_hunks,
    generate_modification_schemes,
    list_modification_schemes,
)
from app.services.llm_errors import LLMInvocationError

router = APIRouter(prefix="/projects/{project_id}/modification-schemes", tags=["modification-schemes"])


@router.get("", response_model=ModificationSchemeListResponse)
async def get_modification_schemes(
    project_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    schemes = await list_modification_schemes(db, project_id, user_id.strip())
    return {"schemes": schemes}


@router.post("/generate", response_model=ModificationSchemeGenerateResponse)
async def post_generate_modification_schemes(
    project_id: str,
    payload: ModificationSchemeGenerateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        result = await generate_modification_schemes(
            db,
            project_id,
            payload.user_id.strip(),
            target_issue_ids=payload.target_issue_ids or None,
            target_position_ids=payload.target_position_ids or None,
            user_message=payload.message,
        )
    except LLMInvocationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc
    return result


@router.post("/{scheme_id}/apply", response_model=ModificationSchemeApplyResponse)
async def post_apply_modification_scheme(
    project_id: str,
    scheme_id: str,
    payload: ModificationSchemeApplyRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        return await apply_modification_scheme_hunks(
            db,
            project_id,
            payload.user_id.strip(),
            scheme_id,
            accepted_hunk_ids=payload.accepted_hunk_ids,
            rejected_hunk_ids=payload.rejected_hunk_ids,
        )
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
