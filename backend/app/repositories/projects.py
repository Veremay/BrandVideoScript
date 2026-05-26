from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.artifact_stale import (
    default_stale,
    mark_brief_changed,
    mark_persona_changed,
    mark_script_changed,
    stale_set_fields,
)
from app.models.script import default_script, new_id, now_iso
from app.models.script_ops import add_column, add_row, delete_column, delete_row, rename_column, update_cell
from app.models.script_validate import normalize_script, validate_script

BRAND_INSIGHT_CATEGORIES = {"explicit_requirement", "implicit_requirement", "brand_feedback"}
BRAND_INSIGHT_CONFIDENCE = {"high", "medium", "low"}
BRAND_INSIGHT_STATUS = {"new", "confirmed", "pending", "ignored"}
PERSONA_AD_SENSITIVITY = {"low", "medium", "high"}
PERSONA_DATA_SOURCES = {"manual", "system_generated", "imported_data"}
PERSONA_OPTIONAL_TEXT_FIELDS = (
    "icon",
    "gender",
    "age_range",
    "preferences",
    "behavior",
    "platform_context",
)
PERSONA_OPTIONAL_LIST_FIELDS = ("trust_trigger", "reject_trigger")
PERSONA_MUTABLE_FIELDS = (
    "name",
    *PERSONA_OPTIONAL_TEXT_FIELDS,
    "ad_sensitivity",
    *PERSONA_OPTIONAL_LIST_FIELDS,
)


def serialize_project(document: dict) -> dict:
    document["_id"] = str(document["_id"])
    if "stale" not in document:
        document["stale"] = default_stale()
    if "current_script_version_id" not in document:
        document["current_script_version_id"] = None
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


def _normalize_persona_list_field(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[str] = []
        for entry in value:
            if entry is None:
                continue
            text = str(entry).strip()
            if text:
                items.append(text[:120])
        return items[:10]
    if isinstance(value, str):
        return [chunk.strip()[:120] for chunk in value.split(",") if chunk.strip()][:10]
    return []


def build_persona(
    *,
    name: str,
    icon: str = "",
    gender: str = "",
    age_range: str = "",
    preferences: str = "",
    behavior: str = "",
    platform_context: str = "",
    ad_sensitivity: str = "medium",
    trust_trigger: list[str] | None = None,
    reject_trigger: list[str] | None = None,
    data_source: str = "manual",
) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Persona name cannot be empty")
    if ad_sensitivity not in PERSONA_AD_SENSITIVITY:
        raise ValueError("Invalid persona ad_sensitivity")
    if data_source not in PERSONA_DATA_SOURCES:
        raise ValueError("Invalid persona data_source")

    now = now_iso()
    return {
        "persona_id": new_id("persona"),
        "name": name[:80],
        "icon": (icon or "").strip()[:8],
        "gender": (gender or "").strip()[:40],
        "age_range": (age_range or "").strip()[:60],
        "preferences": (preferences or "").strip()[:600],
        "behavior": (behavior or "").strip()[:600],
        "platform_context": (platform_context or "").strip()[:200],
        "ad_sensitivity": ad_sensitivity,
        "trust_trigger": _normalize_persona_list_field(trust_trigger),
        "reject_trigger": _normalize_persona_list_field(reject_trigger),
        "data_source": data_source,
        "created_at": now,
        "updated_at": now,
    }


def update_persona_in_list(personas: list[dict], persona_id: str, changes: dict) -> list[dict]:
    found = False
    updated_personas: list[dict] = []

    for persona in personas:
        if persona.get("persona_id") != persona_id:
            updated_personas.append(persona)
            continue

        found = True
        next_persona = {**persona}
        for field, value in changes.items():
            if field not in PERSONA_MUTABLE_FIELDS or value is None:
                continue
            if field in PERSONA_OPTIONAL_LIST_FIELDS:
                next_persona[field] = _normalize_persona_list_field(value)
            elif isinstance(value, str):
                next_persona[field] = value.strip()
            else:
                next_persona[field] = value

        if not str(next_persona.get("name") or "").strip():
            raise ValueError("Persona name cannot be empty")
        if next_persona.get("ad_sensitivity") not in PERSONA_AD_SENSITIVITY:
            raise ValueError("Invalid persona ad_sensitivity")
        next_persona["updated_at"] = _next_timestamp_after(persona.get("updated_at"))
        updated_personas.append(next_persona)

    if not found:
        raise ValueError("Persona not found")
    return updated_personas


def remove_persona_from_list(personas: list[dict], persona_id: str) -> list[dict]:
    updated = [persona for persona in personas if persona.get("persona_id") != persona_id]
    if len(updated) == len(personas):
        raise ValueError("Persona not found")
    return updated


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
        "rationale_nodes": [],
        "rationale_edges": [],
        "modification_schemes": [],
        "negotiation_queue": [],
        "negotiation_preparation": None,
        "current_script_version_id": new_id("script_ver"),
        "stale": default_stale(),
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
    brief = build_brief(filename=filename, text=text)
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"brief": brief, "updated_at": now_iso(), **stale_set_fields(mark_brief_changed())}},
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


async def create_persona(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    name: str,
    icon: str = "",
    gender: str = "",
    age_range: str = "",
    preferences: str = "",
    behavior: str = "",
    platform_context: str = "",
    ad_sensitivity: str = "medium",
    trust_trigger: list[str] | None = None,
    reject_trigger: list[str] | None = None,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    persona = build_persona(
        name=name,
        icon=icon,
        gender=gender,
        age_range=age_range,
        preferences=preferences,
        behavior=behavior,
        platform_context=platform_context,
        ad_sensitivity=ad_sensitivity,
        trust_trigger=trust_trigger,
        reject_trigger=reject_trigger,
    )
    personas = [*project.get("personas", []), persona]
    active_id = project.get("active_persona_id") or persona["persona_id"]
    return await _write_personas(db, project_id, user_id, personas=personas, active_persona_id=active_id)


async def update_persona(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    persona_id: str,
    changes: dict,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    personas = update_persona_in_list(project.get("personas", []), persona_id, changes)
    return await _write_personas(db, project_id, user_id, personas=personas, active_persona_id=project.get("active_persona_id"))


async def delete_persona(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    persona_id: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    personas = remove_persona_from_list(project.get("personas", []), persona_id)

    active_id = project.get("active_persona_id")
    if active_id == persona_id:
        active_id = personas[0]["persona_id"] if personas else None

    return await _write_personas(db, project_id, user_id, personas=personas, active_persona_id=active_id)


async def set_active_persona(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    persona_id: str | None,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    personas = project.get("personas", [])
    if persona_id is not None and not any(p.get("persona_id") == persona_id for p in personas):
        raise ValueError("Persona not found")

    return await _write_personas(db, project_id, user_id, personas=personas, active_persona_id=persona_id)


async def _write_personas(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    personas: list[dict],
    active_persona_id: str | None,
) -> dict | None:
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "personas": personas,
                "active_persona_id": active_persona_id,
                "updated_at": now_iso(),
                **stale_set_fields(mark_persona_changed()),
            }
        },
    )
    return await get_project(db, project_id, user_id)


async def _write_brand_insights(db: AsyncIOMotorDatabase, project_id: str, user_id: str, insights: list[dict]) -> dict | None:
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "brand_insights": insights,
                "updated_at": now_iso(),
                "stale.modification_schemes": "stale_graph_changed",
            }
        },
    )
    return await get_project(db, project_id, user_id)


async def _write_script(db: AsyncIOMotorDatabase, project_id: str, user_id: str, script: dict) -> dict | None:
    normalized = normalize_script(script)
    validate_script(normalized)
    normalized["updated_at"] = now_iso()
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "current_script": normalized,
                "updated_at": normalized["updated_at"],
                **stale_set_fields(mark_script_changed()),
            }
        },
    )
    return await get_project(db, project_id, user_id)
