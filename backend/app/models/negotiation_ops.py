from __future__ import annotations

from typing import Any

from app.models.script import new_id, now_iso


def _as_str(value: Any, *, limit: int = 2000) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _as_str_list(value: Any, *, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [_as_str(item, limit=600) for item in value]
    return [item for item in items if item][:limit]


def _normalize_script_refs(value: Any) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    if not isinstance(value, list):
        return refs
    for item in value:
        if not isinstance(item, dict):
            continue
        row_id = _as_str(item.get("row_id"), limit=80)
        if not row_id:
            continue
        refs.append(
            {
                "row_id": row_id,
                "column_id": _as_str(item.get("column_id"), limit=80),
                "text_snapshot": _as_str(item.get("text_snapshot"), limit=600),
            }
        )
    return refs


def _normalize_dispute(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    # Support both new streamlined fields and legacy fields
    issue_node_id = _as_str(item.get("issue_node_id"), limit=80)
    brand_feedback = _as_str(item.get("brand_feedback")) or _as_str(item.get("summary"))
    reply = _as_str(item.get("reply")) or _as_str(item.get("our_position"))
    fallback = _as_str(item.get("fallback")) or _as_str(item.get("acceptable_concession"))
    if not issue_node_id and not brand_feedback and not reply:
        return None
    return {
        "issue_node_id": issue_node_id,
        "brand_feedback": brand_feedback,
        "reply": reply,
        "fallback": fallback,
        "talking_points": _as_str_list(item.get("talking_points")),
        # Legacy fields preserved for backward compatibility
        "summary": _as_str(item.get("summary")),
        "our_position": _as_str(item.get("our_position")),
        "acceptable_concession": _as_str(item.get("acceptable_concession")),
        "non_negotiable_line": _as_str(item.get("non_negotiable_line")),
        "related_node_ids": _as_str_list(item.get("related_node_ids"), limit=40),
        "related_script_refs": _normalize_script_refs(item.get("related_script_refs")),
    }


def build_negotiation_preparation(
    payload: dict[str, Any],
    *,
    project_id: str,
    script_version_id: str | None = None,
    related_issue_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Normalize an LLM/mock payload into a NegotiationPreparation document.

    See docs/data_structures.md §10.
    """
    now = now_iso()
    disputes = [
        dispute
        for dispute in (_normalize_dispute(item) for item in (payload.get("open_disputes") or []))
        if dispute is not None
    ]
    order = _as_str_list(payload.get("recommended_communication_order"), limit=40)
    # Default the order to the dispute node ids if the model omitted it.
    if not order:
        order = [d["issue_node_id"] for d in disputes if d.get("issue_node_id")]

    return {
        "prep_id": new_id("prep"),
        "project_id": project_id,
        "title": _as_str(payload.get("title"), limit=120) or "协商沟通方案",
        "based_on_script_version_id": script_version_id,
        "design_intent": _as_str(payload.get("design_intent")),
        "satisfied_brand_needs": _as_str_list(payload.get("satisfied_brand_needs")),
        "open_disputes": disputes,
        "recommended_communication_order": order,
        "related_issue_ids": list(related_issue_ids or []),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
