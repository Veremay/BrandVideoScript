from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import ShareFeedbackPatchRequest, ShareFeedbackPatchResponse, ShareScriptResponse
from app.repositories.share_sessions import get_share_script, patch_share_feedback_cell

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/{share_token}", response_model=ShareScriptResponse)
async def get_shared_script(
    share_token: str,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    payload = await get_share_script(db, share_token.strip())
    if payload is None:
        raise HTTPException(status_code=404, detail="Share link not found or expired")
    return payload


@router.patch("/{share_token}/feedback", response_model=ShareFeedbackPatchResponse)
async def save_shared_feedback(
    share_token: str,
    payload: ShareFeedbackPatchRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    try:
        script = await patch_share_feedback_cell(
            db,
            share_token.strip(),
            payload.row_id.strip(),
            payload.column_id.strip(),
            payload.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if script is None:
        raise HTTPException(status_code=404, detail="Share link not found or expired")
    return {"script": script}
