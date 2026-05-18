from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
    ScriptPatchRequest,
)
from app.repositories.projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    patch_script,
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

