"""User mutation audit logging with before/after state slices."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.activity_logs import insert_activity_log
from app.services.app_log import activity_log_enabled, get_request_id, log_activity, log_error


def script_slice(script: dict[str, Any] | None) -> dict[str, Any] | None:
    """Full script content: columns + rows with cell values."""
    if script is None:
        return None
    columns = []
    for column in script.get("columns") or []:
        columns.append(
            {
                "column_id": column.get("column_id"),
                "key": column.get("key"),
                "label": column.get("label"),
                "type": column.get("type"),
                "multiline": column.get("multiline"),
                "order": column.get("order"),
            }
        )
    rows = []
    for row in script.get("rows") or []:
        rows.append(
            {
                "row_id": row.get("row_id"),
                "order": row.get("order"),
                "cells": [
                    {"column_id": cell.get("column_id"), "value": cell.get("value", "")}
                    for cell in (row.get("cells") or [])
                ],
            }
        )
    return {
        "settings": deepcopy(script.get("settings") or {}),
        "columns": columns,
        "rows": rows,
        "updated_at": script.get("updated_at"),
    }


def node_slice(node: dict[str, Any] | None) -> dict[str, Any] | None:
    if node is None:
        return None
    return {
        "node_id": node.get("node_id"),
        "node_type": node.get("node_type"),
        "title": node.get("title"),
        "content": node.get("content"),
        "source_type": node.get("source_type"),
        "source_perspective": node.get("source_perspective"),
        "status": node.get("status"),
        "stance": node.get("stance"),
        "confidence": node.get("confidence"),
        "in_consideration_queue": node.get("in_consideration_queue"),
        "in_communication_support_queue": node.get("in_communication_support_queue"),
        "linked_script_refs": deepcopy(node.get("linked_script_refs") or []),
        "layout": deepcopy(node.get("layout") or {}),
        "conflict_tags": list(node.get("conflict_tags") or []),
        "business_tags": list(node.get("business_tags") or []),
    }


def nodes_slice(nodes: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [item for item in (node_slice(node) for node in (nodes or [])) if item is not None]


def edge_slice(edge: dict[str, Any] | None) -> dict[str, Any] | None:
    if edge is None:
        return None
    return {
        "edge_id": edge.get("edge_id"),
        "from_node_id": edge.get("from_node_id"),
        "to_node_id": edge.get("to_node_id"),
        "relation_type": edge.get("relation_type"),
    }


def hunk_slice(hunk: dict[str, Any] | None) -> dict[str, Any] | None:
    if hunk is None:
        return None
    return {
        "hunk_id": hunk.get("hunk_id"),
        "row_id": hunk.get("row_id"),
        "column_id": hunk.get("column_id"),
        "context": hunk.get("context"),
        "removed": hunk.get("removed"),
        "added": hunk.get("added"),
        "decision": hunk.get("decision"),
    }


def hunks_slice(hunks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [item for item in (hunk_slice(hunk) for hunk in (hunks or [])) if item is not None]


def brief_slice(brief: dict[str, Any] | None) -> dict[str, Any] | None:
    if brief is None:
        return None
    return {
        "filename": brief.get("filename"),
        "text": brief.get("text"),
        "updated_at": brief.get("updated_at"),
    }


def persona_slice(persona: dict[str, Any] | None) -> dict[str, Any] | None:
    if persona is None:
        return None
    return {
        "persona_id": persona.get("persona_id"),
        "name": persona.get("name"),
        "job": persona.get("job"),
        "explanation": persona.get("explanation"),
        "reason": persona.get("reason"),
        "personal_experiences": list(persona.get("personal_experiences") or []),
        "characteristic_values": deepcopy(persona.get("characteristic_values") or {}),
    }


def brand_insight_slice(insight: dict[str, Any] | None) -> dict[str, Any] | None:
    if insight is None:
        return None
    return {
        "insight_id": insight.get("insight_id"),
        "category": insight.get("category"),
        "title": insight.get("title"),
        "content": insight.get("content"),
        "reason": insight.get("reason"),
        "evidence": insight.get("evidence"),
        "confidence": insight.get("confidence"),
        "status": insight.get("status"),
    }


def project_summary_slice(project: dict[str, Any] | None) -> dict[str, Any] | None:
    if project is None:
        return None
    return {
        "project_id": project.get("project_id") or project.get("_id"),
        "title": project.get("title"),
        "video_category": project.get("video_category"),
        "mode": project.get("mode"),
        "script": script_slice(project.get("current_script")),
        "nodes": nodes_slice(project.get("rationale_nodes")),
        "brief": brief_slice(project.get("brief")),
    }


def build_mutation_event(
    *,
    action: str,
    user_id: str | None,
    project_id: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    request_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.models.script import new_id, now_iso

    event: dict[str, Any] = {
        "event_id": new_id("evt"),
        "event_type": "mutation",
        "ts": now_iso(),
        "action": action,
        "request_id": request_id or get_request_id() or None,
        "source": "repository",
    }
    if user_id:
        event["user_id"] = user_id
    if project_id:
        event["project_id"] = project_id
    if before is not None:
        event["before"] = before
    if after is not None:
        event["after"] = after
    if meta:
        event["meta"] = meta
    return event


async def record_mutation(
    db: AsyncIOMotorDatabase,
    *,
    action: str,
    user_id: str | None = None,
    project_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    log_activity(
        action=action,
        user_id=user_id,
        project_id=project_id,
        before=before,
        after=after,
        meta=meta,
    )
    if not activity_log_enabled():
        return
    try:
        event = build_mutation_event(
            action=action,
            user_id=user_id,
            project_id=project_id,
            before=before,
            after=after,
            meta=meta,
        )
        await insert_activity_log(db, event)
    except Exception as exc:
        log_error("Failed to persist mutation audit log", exc=exc, action=action, project_id=project_id)
