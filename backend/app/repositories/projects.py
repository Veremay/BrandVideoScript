from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import default_script, new_id, now_iso
from app.models.script_ops import add_column, add_row, delete_column, delete_row, rename_column, update_cell


def serialize_project(document: dict) -> dict:
    document["_id"] = str(document["_id"])
    return document


async def enter_user(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    now = now_iso()
    await db.users.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"_id": user_id, "created_at": now}},
        upsert=True,
    )
    user = await db.users.find_one({"_id": user_id})
    return {"user_id": user["_id"], "created_at": user["created_at"]}


async def create_project(db: AsyncIOMotorDatabase, user_id: str, title: str) -> dict:
    await enter_user(db, user_id)
    now = now_iso()
    project = {
        "_id": new_id("project"),
        "user_id": user_id,
        "title": title,
        "brief": {
            "filename": None,
            "text": "",
            "summary": "",
            "parse_status": "pending",
            "uploaded_at": None,
        },
        "current_script": default_script(),
        "brand_insights": [],
        "personas": [],
        "active_persona_id": None,
        "audience_analysis": {},
        "expert_suggestions": [],
        "stale": {"brand": False, "audience": False, "expert": False},
        "created_at": now,
        "updated_at": now,
    }
    await db.projects.insert_one(project)
    return serialize_project(project)


async def list_projects(db: AsyncIOMotorDatabase, user_id: str) -> list[dict]:
    cursor = db.projects.find({"user_id": user_id}).sort("updated_at", -1)
    return [serialize_project(project) async for project in cursor]


async def get_project(db: AsyncIOMotorDatabase, project_id: str, user_id: str) -> dict | None:
    project = await db.projects.find_one({"_id": project_id, "user_id": user_id})
    return serialize_project(project) if project else None


async def update_project(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    title: str | None = None,
) -> dict | None:
    update: dict = {"updated_at": now_iso()}
    if title is not None:
        update["title"] = title
    await db.projects.update_one({"_id": project_id, "user_id": user_id}, {"$set": update})
    return await get_project(db, project_id, user_id)


async def delete_project(db: AsyncIOMotorDatabase, project_id: str, user_id: str) -> bool:
    result = await db.projects.delete_one({"_id": project_id, "user_id": user_id})
    return result.deleted_count == 1


async def patch_script(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    script: dict,
) -> dict | None:
    return await _write_script(db, project_id, user_id, script)


async def patch_script_cell(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    row_id: str,
    column_id: str,
    value: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    return await _write_script(db, project_id, user_id, update_cell(project["current_script"], row_id, column_id, value))


async def create_script_row(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    after_row_id: str | None,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    return await _write_script(db, project_id, user_id, add_row(project["current_script"], after_row_id))


async def remove_script_row(db: AsyncIOMotorDatabase, project_id: str, user_id: str, row_id: str) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    return await _write_script(db, project_id, user_id, delete_row(project["current_script"], row_id))


async def create_script_column(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    after_column_id: str | None,
    label: str,
    column_type: str,
    multiline: bool,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    script = add_column(
        project["current_script"],
        after_column_id=after_column_id,
        label=label,
        column_type=column_type,
        multiline=multiline,
    )
    return await _write_script(db, project_id, user_id, script)


async def update_script_column(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    column_id: str,
    label: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    return await _write_script(db, project_id, user_id, rename_column(project["current_script"], column_id, label))


async def remove_script_column(db: AsyncIOMotorDatabase, project_id: str, user_id: str, column_id: str) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    return await _write_script(db, project_id, user_id, delete_column(project["current_script"], column_id))


async def _write_script(db: AsyncIOMotorDatabase, project_id: str, user_id: str, script: dict) -> dict | None:
    script["updated_at"] = now_iso()
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "current_script": script,
                "stale": {"brand": True, "audience": True, "expert": True},
                "updated_at": now_iso(),
            }
        },
    )
    return await get_project(db, project_id, user_id)
