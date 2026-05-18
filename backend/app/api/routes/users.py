from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import UserEnterRequest, UserResponse
from app.repositories.projects import enter_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/enter", response_model=UserResponse)
async def enter(
    payload: UserEnterRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    return await enter_user(db, payload.user_id.strip())

