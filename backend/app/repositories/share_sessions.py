import secrets
from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.artifact_stale import mark_brand_feedback_changed, stale_set_fields
from app.models.script import now_iso
from app.models.script_ops import update_brand_feedback_cell
from app.models.script_validate import normalize_script, validate_script
from app.repositories.projects import get_project, get_project_by_id
from app.services.audit_log import record_mutation, script_slice

SHARE_TOKEN_BYTES = 32
DEFAULT_SHARE_TTL_DAYS = 90


def _is_active_session(session: dict, now: str) -> bool:
    expires_at = session.get("expires_at")
    if expires_at is None:
        return True
    return isinstance(expires_at, str) and expires_at > now


async def get_share_session(db: AsyncIOMotorDatabase, share_token: str) -> dict | None:
    document = await db.share_sessions.find_one({"_id": share_token})
    if document is None:
        return None
    document["share_token"] = str(document["_id"])
    return document


async def create_or_get_share_session(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    now = now_iso()
    existing = await db.share_sessions.find_one({"project_id": project_id}, sort=[("created_at", -1)])
    if existing is not None and _is_active_session(existing, now):
        existing["share_token"] = str(existing["_id"])
        return existing

    expires_at = (datetime.now(UTC) + timedelta(days=DEFAULT_SHARE_TTL_DAYS)).isoformat()
    share_token = secrets.token_urlsafe(SHARE_TOKEN_BYTES)
    document = {
        "_id": share_token,
        "project_id": project_id,
        "created_at": now,
        "expires_at": expires_at,
    }
    await db.share_sessions.insert_one(document)
    document["share_token"] = share_token
    return document


async def get_share_script(db: AsyncIOMotorDatabase, share_token: str) -> dict | None:
    session = await get_share_session(db, share_token)
    if session is None or not _is_active_session(session, now_iso()):
        return None

    project = await get_project_by_id(db, session["project_id"])
    if project is None:
        return None

    return {
        "title": project.get("title", "Script"),
        "script": project["current_script"],
        "expires_at": session.get("expires_at"),
    }


async def patch_share_feedback_cell(
    db: AsyncIOMotorDatabase,
    share_token: str,
    row_id: str,
    column_id: str,
    value: str,
) -> dict | None:
    session = await get_share_session(db, share_token)
    if session is None or not _is_active_session(session, now_iso()):
        return None

    project = await get_project_by_id(db, session["project_id"])
    if project is None:
        return None

    before_script = script_slice(project["current_script"])
    try:
        updated_script = update_brand_feedback_cell(project["current_script"], row_id, column_id, value)
    except ValueError:
        raise

    normalized = normalize_script(updated_script)
    validate_script(normalized)
    normalized["updated_at"] = now_iso()

    await db.projects.update_one(
        {"_id": session["project_id"]},
        {
            "$set": {
                "current_script": normalized,
                "updated_at": normalized["updated_at"],
                **stale_set_fields(mark_brand_feedback_changed()),
            }
        },
    )
    await record_mutation(
        db,
        action="share.feedback.save",
        user_id=session.get("user_id"),
        project_id=session["project_id"],
        before={"script": before_script},
        after={"script": script_slice(normalized)},
        meta={"share_token": share_token, "row_id": row_id, "column_id": column_id, "value": value},
    )
    return normalized
