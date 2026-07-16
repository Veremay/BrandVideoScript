from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import (
    ActivePersonaUpdateRequest,
    ActivityLogListResponse,
    BriefParseRequest,
    BriefParseResponse,
    BriefUpdateRequest,
    GraphResponse,
    BrandInsightCreateRequest,
    BrandInsightUpdateRequest,
    BrandRequirementsUpdateRequest,
    PersonaCreateRequest,
    PersonaProvisionRequest,
    PersonaProvisionResponse,
    PersonaUpdateRequest,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ScriptCellPatchRequest,
    ScriptColumnCreateRequest,
    ScriptColumnUpdateRequest,
    ProjectUpdateRequest,
    ScriptPatchRequest,
    ScriptRowCreateRequest,
    ScriptSnapshotCreateRequest,
    ScriptSnapshotCreateResponse,
    ScriptSnapshotListResponse,
    ShareCreateRequest,
    ShareCreateResponse,
)
from app.repositories.activity_logs import list_project_activity_logs
from app.repositories.script_snapshots import create_script_snapshot, list_script_snapshots, restore_script_snapshot
from app.repositories.share_sessions import create_or_get_share_session
from app.services.coordinator_service import provision_personas_from_analytics, run_brief_initial_parse, stream_brief_parse
from app.repositories.projects import (
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
    set_active_persona,
    update_brand_insight,
    update_brand_requirements,
    update_brief,
    update_persona,
    update_script_column,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_user_projects(
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    return {"projects": await list_projects(db, user_id)}


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create(payload: ProjectCreateRequest, db: AsyncIOMotorDatabase = Depends(database_dependency)) -> dict:
    return await create_project(
        db,
        payload.user_id.strip(),
        payload.title.strip(),
        video_category=payload.video_category,
        mode=payload.mode,
    )


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


@router.get("/{project_id}/activity-logs", response_model=ActivityLogListResponse)
async def get_project_activity_logs(
    project_id: str,
    user_id: str = Query(min_length=1),
    download: bool = Query(default=False, description="Return as a downloadable JSON file"),
    event_type: str | None = Query(default="mutation", description="Filter by event_type; omit or empty for all"),
    action: str | None = Query(default=None, description="Optional exact action filter, e.g. scheme.hunks.decide"),
    limit: int = Query(default=5000, ge=1, le=20000),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict | JSONResponse:
    project = await get_project(db, project_id, user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    normalized_event_type = None
    if isinstance(event_type, str):
        stripped = event_type.strip()
        if stripped and stripped.lower() != "all":
            normalized_event_type = stripped
    events = await list_project_activity_logs(
        db,
        project_id,
        event_type=normalized_event_type,
        action=action.strip() if action else None,
        limit=limit,
    )
    payload = {
        "project_id": project_id,
        "count": len(events),
        "events": events,
    }
    if not download:
        return payload

    filename = f"activity_logs_{project_id}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        media_type="application/json",
    )


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
    return project


@router.get("/{project_id}/graph", response_model=GraphResponse)
async def get_project_graph(
    project_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "rationale_nodes": project.get("rationale_nodes", []),
        "rationale_edges": project.get("rationale_edges", []),
        "updated_at": project.get("updated_at", ""),
    }


@router.post("/{project_id}/brief/parse", response_model=BriefParseResponse)
async def parse_brief(
    project_id: str,
    payload: BriefParseRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        return await run_brief_initial_parse(db, project_id, payload.user_id.strip())
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == "Project not found" else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.post("/{project_id}/brief/parse/stream")
async def parse_brief_stream(
    project_id: str,
    payload: BriefParseRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> StreamingResponse:
    return StreamingResponse(
        stream_brief_parse(db, project_id, payload.user_id.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{project_id}/persona/provision-from-analytics", response_model=PersonaProvisionResponse)
async def provision_persona_from_analytics(
    project_id: str,
    payload: PersonaProvisionRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        return await provision_personas_from_analytics(
            db,
            project_id,
            payload.user_id.strip(),
            platform_context=payload.platform_context,
            content_category=payload.content_category,
            brand_name=payload.brand_name,
            video_topic=payload.video_topic,
            run_audience_parse=payload.run_audience_parse,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == "Project not found" else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.patch("/{project_id}/brand/requirements", response_model=ProjectResponse)
async def save_brand_requirements(
    project_id: str,
    payload: BrandRequirementsUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    brand_insights = [item.model_dump() for item in payload.brand_insights]
    project = await update_brand_requirements(
        db,
        project_id,
        payload.user_id.strip(),
        brand_insights=brand_insights,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
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


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    project_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> None:
    deleted = await delete_project(db, project_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/share", response_model=ShareCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_share_link(
    project_id: str,
    payload: ShareCreateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    session = await create_or_get_share_session(db, project_id, payload.user_id.strip())
    if session is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "share_token": session["share_token"],
        "expires_at": session.get("expires_at"),
    }


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
    try:
        project = await patch_script(db, project_id, payload.user_id.strip(), payload.script)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/script/snapshots", response_model=ScriptSnapshotListResponse)
async def get_script_snapshots(
    project_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, user_id.strip())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    snapshots = await list_script_snapshots(db, project_id, user_id.strip())
    return {"snapshots": snapshots}


@router.post(
    "/{project_id}/script/snapshots",
    response_model=ScriptSnapshotCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_script_snapshot(
    project_id: str,
    payload: ScriptSnapshotCreateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        snapshot = await create_script_snapshot(
            db,
            project_id,
            payload.user_id.strip(),
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"snapshot": snapshot}


@router.post("/{project_id}/script/snapshots/{snapshot_id}/restore", response_model=ProjectResponse)
async def restore_snapshot(
    project_id: str,
    snapshot_id: str,
    user_id: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await restore_script_snapshot(db, project_id, user_id.strip(), snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc
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
            job=payload.job,
            explanation=payload.explanation,
            reason=payload.reason,
            personal_experiences=(
                payload.personal_experiences
                if isinstance(payload.personal_experiences, list)
                else payload.personal_experiences
            ),
            characteristic_values=payload.characteristic_values,
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
    if "personal_experiences" in changes and isinstance(changes["personal_experiences"], str):
        changes["personal_experiences"] = [
            chunk.strip() for chunk in changes["personal_experiences"].replace("\r", "").split("\n") if chunk.strip()
        ]
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
async def update_active_persona(
    project_id: str,
    payload: ActivePersonaUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        project = await set_active_persona(db, project_id, payload.user_id.strip(), payload.persona_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
