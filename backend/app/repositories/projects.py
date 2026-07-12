from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.artifact_stale import (
    default_stale,
    mark_brief_changed,
    mark_persona_changed,
    mark_script_changed,
    stale_set_fields,
)
from app.models.choice_history import normalize_choice_history
from app.models.script import default_script, new_id, now_iso
from app.models.script_ops import (
    add_column,
    add_row,
    delete_column,
    delete_row,
    preserve_brand_feedback_cells,
    rename_column,
    update_cell,
)
from app.models.script_validate import normalize_script, validate_script
from app.services.audit_log import (
    brand_insight_slice,
    brief_slice,
    persona_slice,
    project_summary_slice,
    record_mutation,
    script_slice,
)

VIDEO_CATEGORIES = frozenset({"lifestyle"})

BRAND_INSIGHT_CATEGORIES = {"explicit_requirement", "implicit_requirement", "brand_feedback"}
BRAND_INSIGHT_CONFIDENCE = {"high", "medium", "low"}
BRAND_INSIGHT_STATUS = {"new", "confirmed", "pending", "ignored"}
PERSONA_DATA_SOURCES = {"manual", "system_generated", "imported_data"}
PERSONA_OPTIONAL_TEXT_FIELDS = ("job", "explanation", "reason")
PERSONA_OPTIONAL_LIST_FIELDS = ("personal_experiences",)
PERSONA_OPTIONAL_DICT_FIELDS = ("characteristic_values",)
PERSONA_MUTABLE_FIELDS = (
    "name",
    *PERSONA_OPTIONAL_TEXT_FIELDS,
    *PERSONA_OPTIONAL_LIST_FIELDS,
    *PERSONA_OPTIONAL_DICT_FIELDS,
)


def serialize_project(document: dict) -> dict:
    document["_id"] = str(document["_id"])
    document.setdefault("mode", "full")
    script = document.get("current_script")
    if isinstance(script, dict):
        script.setdefault(
            "settings",
            {
                "mode": document["mode"],
                "system_support_enabled": document["mode"] == "full",
            },
        )
    if "stale" not in document:
        document["stale"] = default_stale()
    if "current_script_version_id" not in document:
        document["current_script_version_id"] = None
    document.setdefault("platform_context", "other")
    document.setdefault("video_category", "lifestyle")
    document.setdefault("brand_perspective_result", None)
    document.setdefault("audience_perspective_result", None)
    document.setdefault("expert_perspective_result", None)
    document.setdefault("rationale_nodes", [])
    document.setdefault("rationale_edges", [])
    document.setdefault("consideration_queue", [])
    if not document.get("consideration_queue") and document.get("negotiation_queue"):
        document["consideration_queue"] = []
    document.setdefault("communication_support_queue", [])
    document["choice_history"] = normalize_choice_history(document.get("choice_history"))
    document.setdefault("negotiation_preparation", None)
    document.setdefault("modification_schemes", [])
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
        "parse_status": "pending",
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


def filter_insights_preserve_user_and_feedback(insights: list[dict]) -> list[dict]:
    """On Brief re-upload, drop agent-generated requirements; keep user items and brand_feedback."""
    return [
        insight
        for insight in insights
        if insight.get("created_by") == "user" or insight.get("category") == "brand_feedback"
    ]


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


def _normalize_persona_list_field(value: object, *, max_item_len: int = 120, max_items: int = 10) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[str] = []
        for entry in value:
            if entry is None:
                continue
            text = str(entry).strip()
            if text:
                items.append(text[:max_item_len])
        return items[:max_items]
    if isinstance(value, str):
        chunks = [chunk.strip()[:max_item_len] for chunk in value.replace("\r", "").split("\n") if chunk.strip()]
        if len(chunks) == 1 and "," in chunks[0]:
            chunks = [chunk.strip()[:max_item_len] for chunk in value.split(",") if chunk.strip()]
        return chunks[:max_items]
    return []


def _normalize_persona_dict_field(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, entry in value.items():
        label = str(key).strip()
        text = str(entry).strip()
        if label and text:
            normalized[label[:80]] = text[:200]
    return normalized


def build_persona(
    *,
    name: str,
    job: str = "",
    explanation: str = "",
    reason: str = "",
    personal_experiences: list[str] | None = None,
    characteristic_values: dict[str, str] | None = None,
    data_source: str = "manual",
) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Persona name cannot be empty")
    if data_source not in PERSONA_DATA_SOURCES:
        raise ValueError("Invalid persona data_source")

    now = now_iso()
    return {
        "persona_id": new_id("persona"),
        "name": name[:80],
        "job": (job or "").strip()[:80],
        "explanation": (explanation or "").strip()[:1000],
        "reason": (reason or "").strip()[:1000],
        "personal_experiences": _normalize_persona_list_field(
            personal_experiences,
            max_item_len=500,
            max_items=10,
        ),
        "characteristic_values": _normalize_persona_dict_field(characteristic_values or {}),
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
                max_item_len = 500 if field == "personal_experiences" else 120
                next_persona[field] = _normalize_persona_list_field(value, max_item_len=max_item_len)
            elif field in PERSONA_OPTIONAL_DICT_FIELDS:
                next_persona[field] = _normalize_persona_dict_field(value)
            elif isinstance(value, str):
                next_persona[field] = value.strip()
            else:
                next_persona[field] = value

        if not str(next_persona.get("name") or "").strip():
            raise ValueError("Persona name cannot be empty")
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


async def create_project(
    db: AsyncIOMotorDatabase,
    user_id: str,
    title: str,
    *,
    video_category: str = "lifestyle",
    mode: str = "full",
) -> dict:
    if video_category not in VIDEO_CATEGORIES:
        raise ValueError("Invalid video category")
    if mode not in {"full", "vanilla"}:
        raise ValueError("Invalid project mode")
    await enter_user(db, user_id)
    now = now_iso()
    project = {
        "_id": new_id("project"),
        "user_id": user_id,
        "title": title,
        "mode": mode,
        "video_category": video_category,
        "brief": {
            "filename": None,
            "text": "",
            "summary": "",
            "parse_status": "pending",
            "uploaded_at": None,
        },
        "current_script": default_script(mode),
        "platform_context": "xiaohongshu",
        "brand_insights": [],
        "brand_perspective_result": None,
        "audience_perspective_result": None,
        "expert_perspective_result": None,
        "personas": [],
        "active_persona_id": None,
        "audience_analysis": {},
        "expert_suggestions": [],
        "rationale_nodes": [],
        "rationale_edges": [],
        "modification_schemes": [],
        "consideration_queue": [],
        "communication_support_queue": [],
        "choice_history": {"adopted_positions": [], "scheme_position_links": []},
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
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    update: dict = {"updated_at": now_iso()}
    if title is not None:
        update["title"] = title
    await db.projects.update_one({"_id": project_id, "user_id": user_id}, {"$set": update})
    if title is not None:
        await record_mutation(
            db,
            action="project.update",
            user_id=user_id,
            project_id=project_id,
            before={"title": project.get("title")},
            after={"title": title},
        )
    return await get_project(db, project_id, user_id)


async def delete_project(db: AsyncIOMotorDatabase, project_id: str, user_id: str) -> bool:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return False
    result = await db.projects.delete_one({"_id": project_id, "user_id": user_id})
    if result.deleted_count == 1:
        await record_mutation(
            db,
            action="project.delete",
            user_id=user_id,
            project_id=project_id,
            before={"project": project_summary_slice(project)},
            after={"project": None},
        )
    return result.deleted_count == 1


async def patch_script(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    script: dict,
) -> dict | None:
    return await _write_script(db, project_id, user_id, script, audit_action="script.save")


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
    return await _write_script(
        db,
        project_id,
        user_id,
        update_cell(project["current_script"], row_id, column_id, value),
        audit_action="script.cell.update",
        audit_meta={"row_id": row_id, "column_id": column_id},
    )


async def create_script_row(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    after_row_id: str | None,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    return await _write_script(
        db,
        project_id,
        user_id,
        add_row(project["current_script"], after_row_id),
        audit_action="script.row.create",
        audit_meta={"after_row_id": after_row_id},
    )


async def remove_script_row(db: AsyncIOMotorDatabase, project_id: str, user_id: str, row_id: str) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    return await _write_script(
        db,
        project_id,
        user_id,
        delete_row(project["current_script"], row_id),
        audit_action="script.row.delete",
        audit_meta={"row_id": row_id},
    )


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
    return await _write_script(
        db,
        project_id,
        user_id,
        script,
        audit_action="script.column.create",
        audit_meta={"label": label, "column_type": column_type},
    )


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
    return await _write_script(
        db,
        project_id,
        user_id,
        rename_column(project["current_script"], column_id, label),
        audit_action="script.column.rename",
        audit_meta={"column_id": column_id, "label": label},
    )


async def remove_script_column(db: AsyncIOMotorDatabase, project_id: str, user_id: str, column_id: str) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    return await _write_script(
        db,
        project_id,
        user_id,
        delete_column(project["current_script"], column_id),
        audit_action="script.column.delete",
        audit_meta={"column_id": column_id},
    )


async def update_brief(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    filename: str | None,
    text: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    brief = build_brief(filename=filename, text=text)
    kept_insights = filter_insights_preserve_user_and_feedback(project.get("brand_insights", []))
    before_brief = brief_slice(project.get("brief"))
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "brief": brief,
                "brand_insights": kept_insights,
                "updated_at": now_iso(),
                **stale_set_fields(mark_brief_changed()),
            }
        },
    )
    await record_mutation(
        db,
        action="brief.update",
        user_id=user_id,
        project_id=project_id,
        before={"brief": before_brief},
        after={"brief": brief_slice(brief)},
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
    return await _write_brand_insights(
        db,
        project_id,
        user_id,
        insights,
        audit_action="brand_insight.create",
        audit_before={"insight": None},
        audit_after={"insight": brand_insight_slice(insight)},
    )


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
    existing = next(
        (item for item in project.get("brand_insights", []) if item.get("insight_id") == insight_id),
        None,
    )
    insights = update_brand_insight_in_list(project.get("brand_insights", []), insight_id, changes)
    updated = next((item for item in insights if item.get("insight_id") == insight_id), None)
    return await _write_brand_insights(
        db,
        project_id,
        user_id,
        insights,
        audit_action="brand_insight.update",
        audit_before={"insight": brand_insight_slice(existing)},
        audit_after={"insight": brand_insight_slice(updated)},
        audit_meta={"insight_id": insight_id},
    )


async def delete_brand_insight(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    insight_id: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    existing = next(
        (item for item in project.get("brand_insights", []) if item.get("insight_id") == insight_id),
        None,
    )
    insights = remove_brand_insight_from_list(project.get("brand_insights", []), insight_id)
    return await _write_brand_insights(
        db,
        project_id,
        user_id,
        insights,
        audit_action="brand_insight.delete",
        audit_before={"insight": brand_insight_slice(existing)},
        audit_after={"insight": None},
        audit_meta={"insight_id": insight_id},
    )


async def create_persona(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    name: str,
    job: str = "",
    explanation: str = "",
    reason: str = "",
    personal_experiences: list[str] | str | None = None,
    characteristic_values: dict[str, str] | None = None,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    persona = build_persona(
        name=name,
        job=job,
        explanation=explanation,
        reason=reason,
        personal_experiences=personal_experiences if isinstance(personal_experiences, list) else None,
        characteristic_values=characteristic_values,
    )
    personas = [*project.get("personas", []), persona]
    active_id = project.get("active_persona_id") or persona["persona_id"]
    return await _write_personas(
        db,
        project_id,
        user_id,
        personas=personas,
        active_persona_id=active_id,
        audit_action="persona.create",
        audit_before={"persona": None},
        audit_after={"persona": persona_slice(persona)},
    )


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
    existing = next((item for item in project.get("personas", []) if item.get("persona_id") == persona_id), None)
    personas = update_persona_in_list(project.get("personas", []), persona_id, changes)
    updated = next((item for item in personas if item.get("persona_id") == persona_id), None)
    return await _write_personas(
        db,
        project_id,
        user_id,
        personas=personas,
        active_persona_id=project.get("active_persona_id"),
        audit_action="persona.update",
        audit_before={"persona": persona_slice(existing)},
        audit_after={"persona": persona_slice(updated)},
        audit_meta={"persona_id": persona_id},
    )


async def delete_persona(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    persona_id: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None
    existing = next((item for item in project.get("personas", []) if item.get("persona_id") == persona_id), None)
    personas = remove_persona_from_list(project.get("personas", []), persona_id)

    active_id = project.get("active_persona_id")
    if active_id == persona_id:
        active_id = personas[0]["persona_id"] if personas else None

    return await _write_personas(
        db,
        project_id,
        user_id,
        personas=personas,
        active_persona_id=active_id,
        audit_action="persona.delete",
        audit_before={"persona": persona_slice(existing)},
        audit_after={"persona": None},
        audit_meta={"persona_id": persona_id},
    )


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

    return await _write_personas(
        db,
        project_id,
        user_id,
        personas=personas,
        active_persona_id=persona_id,
        audit_action="persona.set_active",
        audit_before={"active_persona_id": project.get("active_persona_id")},
        audit_after={"active_persona_id": persona_id},
    )


async def _write_personas(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    personas: list[dict],
    active_persona_id: str | None,
    audit_action: str | None = None,
    audit_before: dict | None = None,
    audit_after: dict | None = None,
    audit_meta: dict | None = None,
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
    if audit_action:
        await record_mutation(
            db,
            action=audit_action,
            user_id=user_id,
            project_id=project_id,
            before=audit_before,
            after=audit_after,
            meta=audit_meta,
        )
    return await get_project(db, project_id, user_id)


def normalize_brand_requirements(items: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        confidence = str(item.get("confidence") or "medium")
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        entry: dict = {"text": text, "confidence": confidence}
        requirement_id = str(item.get("id") or "").strip()
        if requirement_id:
            entry["id"] = requirement_id
        evidence = str(item.get("evidence") or "").strip()
        if evidence:
            entry["evidence"] = evidence[:2000]
        source = str(item.get("source", "")).strip()
        if source in {"user", "agent"}:
            entry["source"] = source
        normalized.append(entry)
    return normalized


def normalize_brand_insights_requirements(
    items: list[dict] | None,
    *,
    existing_by_id: dict[str, dict] | None = None,
) -> list[dict]:
    """Normalize requirement-category brand insights for persistence."""
    existing_by_id = existing_by_id or {}
    normalized: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        category = str(item.get("category") or "explicit_requirement").strip()
        if category not in {"explicit_requirement", "implicit_requirement"}:
            continue
        confidence = str(item.get("confidence") or "medium")
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        status = str(item.get("status") or "new")
        if status not in {"new", "confirmed", "pending", "ignored"}:
            status = "new"
        insight_id = str(item.get("insight_id") or "").strip()
        existing = existing_by_id.get(insight_id) if insight_id else None
        created_by = str(item.get("created_by") or (existing or {}).get("created_by") or "user")
        if created_by not in {"user", "agent"}:
            created_by = "user"
        now = now_iso()
        if existing:
            normalized.append({
                **existing,
                "insight_id": insight_id,
                "agent_type": "brand",
                "category": category,
                "title": str(item.get("title") or existing.get("title") or "").strip()[:120],
                "content": content,
                "reason": str(item.get("reason") or existing.get("reason") or "").strip(),
                "confidence": confidence,
                "status": status,
                "updated_by": "user",
                "updated_at": now,
            })
            continue
        normalized.append(
            build_brand_insight(
                category=category,
                title=str(item.get("title") or "").strip()[:120] or "Brand requirement",
                content=content,
                reason=str(item.get("reason") or "").strip(),
                evidence=item.get("evidence") if isinstance(item.get("evidence"), list) else [],
                confidence=confidence,
                status=status,
                created_by=created_by,
            )
            if not insight_id
            else {
                "insight_id": insight_id,
                "agent_type": "brand",
                "category": category,
                "title": str(item.get("title") or "").strip()[:120] or "Brand requirement",
                "content": content,
                "reason": str(item.get("reason") or "").strip(),
                "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
                "confidence": confidence,
                "status": status,
                "created_by": created_by,
                "updated_by": "user",
                "based_on_script_version_id": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    return normalized


async def update_brand_requirements(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    brand_insights: list[dict],
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    existing = project.get("brand_insights") or []
    existing_by_id = {
        str(i.get("insight_id")): i
        for i in existing
        if isinstance(i, dict) and i.get("insight_id")
    }
    preserved = [
        i for i in existing
        if isinstance(i, dict) and i.get("category") == "brand_feedback"
    ]
    requirement_insights = normalize_brand_insights_requirements(
        brand_insights,
        existing_by_id=existing_by_id,
    )
    merged_insights = [*requirement_insights, *preserved]
    before_insights = [brand_insight_slice(item) for item in existing if isinstance(item, dict)]
    result = await _write_brand_insights(db, project_id, user_id, merged_insights)
    if result is not None:
        after_insights = [brand_insight_slice(item) for item in merged_insights if isinstance(item, dict)]
        await record_mutation(
            db,
            action="brand_requirements.update",
            user_id=user_id,
            project_id=project_id,
            before={"brand_insights": before_insights},
            after={"brand_insights": after_insights},
        )
    return result


async def _write_brand_insights(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    insights: list[dict],
    *,
    audit_action: str | None = None,
    audit_before: dict | None = None,
    audit_after: dict | None = None,
    audit_meta: dict | None = None,
) -> dict | None:
    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "brand_insights": insights,
                "updated_at": now_iso(),
                **stale_set_fields(mark_brief_changed()),
            }
        },
    )
    if audit_action:
        await record_mutation(
            db,
            action=audit_action,
            user_id=user_id,
            project_id=project_id,
            before=audit_before,
            after=audit_after,
            meta=audit_meta,
        )
    return await get_project(db, project_id, user_id)


async def get_project_by_id(db: AsyncIOMotorDatabase, project_id: str) -> dict | None:
    document = await db.projects.find_one({"_id": project_id})
    if document is None:
        return None
    return serialize_project(document)


async def _write_script(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    script: dict,
    *,
    audit_action: str,
    audit_meta: dict | None = None,
) -> dict | None:
    from app.repositories.script_snapshots import create_script_snapshot

    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    before_script = script_slice(project["current_script"])
    script = preserve_brand_feedback_cells(script, project["current_script"])

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
    await create_script_snapshot(
        db,
        project_id,
        user_id,
        reason="auto_save",
        script=normalized,
    )
    await record_mutation(
        db,
        action=audit_action,
        user_id=user_id,
        project_id=project_id,
        before={"script": before_script},
        after={"script": script_slice(normalized)},
        meta=audit_meta,
    )
    return await get_project(db, project_id, user_id)
