from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import (
    ActivePersonaUpdateRequest,
    BriefUpdateRequest,
    BrandInsightCreateRequest,
    BrandInsightUpdateRequest,
    ExpertSuggestionApplyRequest,
    ExpertSuggestionApplyResponse,
    ExpertSuggestionStatusRequest,
    PersonaCreateRequest,
    PersonaUpdateRequest,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ScriptCellPatchRequest,
    ScriptColumnCreateRequest,
    ScriptColumnUpdateRequest,
    ScriptSnapshotsResponse,
    ProjectUpdateRequest,
    ScriptPatchRequest,
    ScriptRowCreateRequest,
    SnapshotCreateRequest,
    SnapshotRestoreRequest,
)
from app.services.brand_brief_pipeline import run_brand_brief_pipeline
from app.repositories.projects import (
    apply_expert_suggestion,
    create_brand_insight,
    create_persona,
    create_script_column,
    create_script_row,
    create_project,
    delete_brand_insight,
    delete_persona,
    delete_project,
    get_project,
    list_projects,
    patch_script,
    patch_script_cell,
    remove_script_column,
    remove_script_row,
    restore_script_snapshot,
    set_active_persona,
    update_brand_insight,
    update_brief,
    update_expert_suggestion_status,
    update_persona,
    update_script_column,
    update_project,
)
from app.repositories.script_snapshots import create_snapshot, list_snapshots

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_user_projects(
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    return {"projects": await list_projects(db, user_id)}


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create(payload: ProjectCreateRequest, db: AsyncIOMotorDatabase = Depends(database_dependency)) -> dict:
    return await create_project(db, payload.user_id.strip(), payload.title.strip())


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_one(
    project_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update(
    project_id: str,
    payload: ProjectUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await update_project(db, project_id, payload.user_id.strip(), title=payload.title.strip() if payload.title else None)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/brief", response_model=ProjectResponse)
async def save_brief(
    project_id: str,
    payload: BriefUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await update_brief(
            db,
            project_id,
            payload.user_id.strip(),
            filename=payload.filename.strip() if payload.filename else None,
            text=payload.text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    uid = payload.user_id.strip()
    background_tasks.add_task(run_brand_brief_pipeline, db, project_id, uid)
    return project


@router.post("/{project_id}/agents/brand/insights", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def add_brand_insight(
    project_id: str,
    payload: BrandInsightCreateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await create_brand_insight(
            db,
            project_id,
            payload.user_id.strip(),
            category=payload.category,
            title=payload.title,
            content=payload.content,
            reason=payload.reason,
            evidence=payload.evidence,
            confidence=payload.confidence,
            status=payload.status,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}/agents/brand/insights/{insight_id}", response_model=ProjectResponse)
async def edit_brand_insight(
    project_id: str,
    insight_id: str,
    payload: BrandInsightUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    changes = payload.model_dump(exclude={"user_id"}, exclude_none=True)
    try:
        project = await update_brand_insight(db, project_id, payload.user_id.strip(), insight_id, changes)
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc) == "Brand insight not found" else 400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}/agents/brand/insights/{insight_id}", response_model=ProjectResponse)
async def remove_brand_insight(
    project_id: str,
    insight_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await delete_brand_insight(db, project_id, user_id.strip(), insight_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/personas", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def add_persona(
    project_id: str,
    payload: PersonaCreateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await create_persona(
            db,
            project_id,
            payload.user_id.strip(),
            name=payload.name,
            gender=payload.gender,
            age_range=payload.age_range,
            preferences=payload.preferences,
            behavior=payload.behavior,
            platform_context=payload.platform_context,
            ad_sensitivity=payload.ad_sensitivity,
            trust_trigger=payload.trust_trigger,
            reject_trigger=payload.reject_trigger,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}/personas/{persona_id}", response_model=ProjectResponse)
async def edit_persona(
    project_id: str,
    persona_id: str,
    payload: PersonaUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    changes = payload.model_dump(exclude={"user_id"}, exclude_none=True)
    try:
        project = await update_persona(db, project_id, payload.user_id.strip(), persona_id, changes)
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc) == "Persona not found" else 400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}/personas/{persona_id}", response_model=ProjectResponse)
async def remove_persona(
    project_id: str,
    persona_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await delete_persona(db, project_id, user_id.strip(), persona_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}/active-persona", response_model=ProjectResponse)
async def switch_active_persona(
    project_id: str,
    payload: ActivePersonaUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await set_active_persona(
            db,
            project_id,
            payload.user_id.strip(),
            payload.persona_id.strip() if isinstance(payload.persona_id, str) and payload.persona_id.strip() else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc) == "Persona not found" else 400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    project_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> None:
    deleted = await delete_project(db, project_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/script")
async def get_script(
    project_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project["current_script"]


@router.patch("/{project_id}/script", response_model=ProjectResponse)
async def save_script(
    project_id: str,
    payload: ScriptPatchRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await patch_script(db, project_id, payload.user_id.strip(), payload.script)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}/script/cells", response_model=ProjectResponse)
async def save_script_cell(
    project_id: str,
    payload: ScriptCellPatchRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await patch_script_cell(
            db,
            project_id,
            payload.user_id.strip(),
            payload.row_id,
            payload.column_id,
            payload.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/script/rows", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def add_script_row(
    project_id: str,
    payload: ScriptRowCreateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await create_script_row(db, project_id, payload.user_id.strip(), payload.after_row_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}/script/rows/{row_id}", response_model=ProjectResponse)
async def delete_script_row(
    project_id: str,
    row_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await remove_script_row(db, project_id, user_id.strip(), row_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/script/columns", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def add_script_column(
    project_id: str,
    payload: ScriptColumnCreateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await create_script_column(
        db,
        project_id,
        payload.user_id.strip(),
        payload.after_column_id,
        payload.label.strip(),
        payload.type,
        payload.multiline,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}/script/columns/{column_id}", response_model=ProjectResponse)
async def rename_script_column(
    project_id: str,
    column_id: str,
    payload: ScriptColumnUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await update_script_column(db, project_id, payload.user_id.strip(), column_id, payload.label.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}/script/columns/{column_id}", response_model=ProjectResponse)
async def delete_script_column(
    project_id: str,
    column_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await remove_script_column(db, project_id, user_id.strip(), column_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post(
    "/{project_id}/expert-suggestions/{suggestion_id}/apply",
    response_model=ExpertSuggestionApplyResponse,
)
async def apply_expert_suggestion_route(
    project_id: str,
    suggestion_id: str,
    payload: ExpertSuggestionApplyRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        result = await apply_expert_suggestion(
            db,
            project_id,
            payload.user_id.strip(),
            suggestion_id,
            accepted_hunk_ids=payload.accepted_hunk_ids,
            rejected_hunk_ids=payload.rejected_hunk_ids,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return result


@router.patch("/{project_id}/expert-suggestions/{suggestion_id}", response_model=ProjectResponse)
async def update_expert_suggestion_route(
    project_id: str,
    suggestion_id: str,
    payload: ExpertSuggestionStatusRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await update_expert_suggestion_status(
            db,
            project_id,
            payload.user_id.strip(),
            suggestion_id,
            status=payload.status,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/script/snapshots", response_model=ScriptSnapshotsResponse)
async def list_script_snapshots(
    project_id: str,
    user_id: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"snapshots": await list_snapshots(db, project_id=project_id, user_id=user_id, limit=limit)}


@router.post("/{project_id}/script/snapshots", status_code=status.HTTP_201_CREATED)
async def save_manual_snapshot(
    project_id: str,
    payload: SnapshotCreateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, payload.user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    snapshot = await create_snapshot(
        db,
        project_id=project_id,
        user_id=payload.user_id.strip(),
        reason=payload.reason,
        script=project.get("current_script", {}) or {},
    )
    return {
        "_id": snapshot["_id"],
        "project_id": snapshot["project_id"],
        "user_id": snapshot["user_id"],
        "reason": snapshot["reason"],
        "suggestion_id": snapshot.get("suggestion_id"),
        "applied_hunk_ids": snapshot.get("applied_hunk_ids", []),
        "created_at": snapshot["created_at"],
    }


@router.post("/{project_id}/script/snapshots/{snapshot_id}/restore", response_model=ProjectResponse)
async def restore_snapshot_route(
    project_id: str,
    snapshot_id: str,
    payload: SnapshotRestoreRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await restore_script_snapshot(db, project_id, payload.user_id.strip(), snapshot_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
