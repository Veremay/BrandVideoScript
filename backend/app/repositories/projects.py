from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import default_script, new_id, now_iso
from app.services.trace import TraceRecorder
from app.models.script_ops import add_column, add_row, delete_column, delete_row, rename_column, update_cell

BRAND_INSIGHT_CATEGORIES = {"explicit_requirement", "implicit_requirement", "brand_feedback"}
BRAND_INSIGHT_CONFIDENCE = {"high", "medium", "low"}
BRAND_INSIGHT_STATUS = {"new", "confirmed", "pending", "ignored"}


def filter_insights_preserve_user_and_feedback(insights: list[dict]) -> list[dict]:
    """After a new Brief upload, drop agent-generated requirements; keep user items and all brand_feedback."""
    return [
        insight
        for insight in insights
        if insight.get("created_by") == "user" or insight.get("category") == "brand_feedback"
    ]


def default_brand_research_idle() -> dict:
    return {
        "status": "idle",
        "brand_slug": None,
        "matched_wiki": False,
        "queries": [],
        "web_snippets": [],
        "wiki_snippets": [],
        "research_summary": "",
        "error_message": None,
        "trace_run_id": None,
        "traces": [],
        "updated_at": None,
    }


def brand_research_running_placeholder(*, trace: TraceRecorder | None = None) -> dict:
    now = now_iso()
    base = {
        "status": "running",
        "brand_slug": None,
        "matched_wiki": False,
        "queries": [],
        "web_snippets": [],
        "wiki_snippets": [],
        "research_summary": "",
        "error_message": None,
        "trace_run_id": None,
        "traces": [],
        "updated_at": now,
    }
    if trace is not None:
        return trace.merge_brand_research(base)
    return base


def serialize_project(document: dict) -> dict:
    document["_id"] = str(document["_id"])
    if not document.get("brand_research"):
        document["brand_research"] = default_brand_research_idle()
    return document


def build_brief(filename: str | None, text: str) -> dict:
    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("Brief text cannot be empty")

    summary = " ".join(line.strip() for line in normalized_text.splitlines() if line.strip())[:240]
    now = now_iso()
    return {
        "filename": filename.strip() if filename else None,
        "text": normalized_text,
        "summary": summary,
        "parse_status": "parsed",
        "uploaded_at": now,
    }


def build_brand_insight(
    *,
    category: str,
    title: str,
    content: str,
    reason: str,
    evidence: list[dict],
    confidence: str = "medium",
    status: str = "new",
    created_by: str = "user",
) -> dict:
    _validate_brand_insight_values(category=category, confidence=confidence, status=status)
    now = now_iso()
    return {
        "insight_id": new_id("insight"),
        "agent_type": "brand",
        "category": category,
        "title": title.strip(),
        "content": content.strip(),
        "reason": reason.strip(),
        "evidence": evidence,
        "confidence": confidence,
        "status": status,
        "created_by": created_by,
        "updated_by": created_by,
        "based_on_script_version_id": None,
        "created_at": now,
        "updated_at": now,
    }


def update_brand_insight_in_list(insights: list[dict], insight_id: str, changes: dict) -> list[dict]:
    allowed_fields = {"category", "title", "content", "reason", "evidence", "confidence", "status"}
    found = False
    updated_insights: list[dict] = []

    for insight in insights:
        if insight.get("insight_id") != insight_id:
            updated_insights.append(insight)
            continue

        found = True
        updated = {**insight}
        for field, value in changes.items():
            if field in allowed_fields and value is not None:
                updated[field] = value.strip() if isinstance(value, str) else value

        _validate_brand_insight_values(
            category=updated.get("category"),
            confidence=updated.get("confidence"),
            status=updated.get("status"),
        )
        updated["updated_by"] = "user"
        updated["updated_at"] = _next_timestamp_after(insight.get("updated_at"))
        updated_insights.append(updated)

    if not found:
        raise ValueError("Brand insight not found")
    return updated_insights


def remove_brand_insight_from_list(insights: list[dict], insight_id: str) -> list[dict]:
    updated = [insight for insight in insights if insight.get("insight_id") != insight_id]
    if len(updated) == len(insights):
        raise ValueError("Brand insight not found")
    return updated


def _validate_brand_insight_values(*, category: str, confidence: str, status: str) -> None:
    if category not in BRAND_INSIGHT_CATEGORIES:
        raise ValueError("Invalid brand insight category")
    if confidence not in BRAND_INSIGHT_CONFIDENCE:
        raise ValueError("Invalid brand insight confidence")
    if status not in BRAND_INSIGHT_STATUS:
        raise ValueError("Invalid brand insight status")


def _next_timestamp_after(previous: str | None) -> str:
    current = now_iso()
    if previous is None or current > previous:
        return current
    return (datetime.fromisoformat(previous) + timedelta(microseconds=1)).isoformat()


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
        "brand_research": default_brand_research_idle(),
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


async def update_brief(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    filename: str | None,
    text: str,
) -> dict | None:
    existing = await db.projects.find_one({"_id": project_id, "user_id": user_id})
    if existing is None:
        return None

    brief = build_brief(filename=filename, text=text)
    kept_insights = filter_insights_preserve_user_and_feedback(existing.get("brand_insights", []))
    trace = TraceRecorder(source="brief_api")
    trace.brief_uploaded(
        filename=brief.get("filename"),
        text_length=len(brief.get("text") or ""),
        summary=brief.get("summary") or "",
    )
    brand_research = brand_research_running_placeholder(trace=trace)

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "brief": brief,
                "brand_insights": kept_insights,
                "brand_research": brand_research,
                "stale.brand": True,
                "stale.expert": True,
                "updated_at": now_iso(),
            }
        },
    )
    return await get_project(db, project_id, user_id)


async def create_brand_insight(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    category: str,
    title: str,
    content: str,
    reason: str,
    evidence: list[dict],
    confidence: str,
    status: str,
    created_by: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    insight = build_brand_insight(
        category=category,
        title=title,
        content=content,
        reason=reason,
        evidence=evidence,
        confidence=confidence,
        status=status,
        created_by=created_by,
    )
    insights = [*project.get("brand_insights", []), insight]
    return await _write_brand_insights(db, project_id, user_id, insights)


async def update_brand_insight(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    insight_id: str,
    changes: dict,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    insights = update_brand_insight_in_list(project.get("brand_insights", []), insight_id, changes)
    return await _write_brand_insights(db, project_id, user_id, insights)


async def delete_brand_insight(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    insight_id: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    insights = remove_brand_insight_from_list(project.get("brand_insights", []), insight_id)
    return await _write_brand_insights(db, project_id, user_id, insights)


async def _write_brand_insights(db: AsyncIOMotorDatabase, project_id: str, user_id: str, insights: list[dict]) -> dict | None:
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"brand_insights": insights, "stale.expert": True, "updated_at": now_iso()}},
    )
    return await get_project(db, project_id, user_id)


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
