from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ScriptCellPatchRequest,
    ScriptColumnCreateRequest,
    ScriptColumnUpdateRequest,
    ProjectUpdateRequest,
    ScriptPatchRequest,
    ScriptRowCreateRequest,
)
from app.repositories.projects import (
    create_script_column,
    create_script_row,
    create_project,
    delete_project,
    get_project,
    list_projects,
    patch_script,
    patch_script_cell,
    remove_script_column,
    remove_script_row,
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
