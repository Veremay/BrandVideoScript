from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.models.script import new_id, now_iso
from app.models.script_ops import update_cell

SCHEME_DIRECTIONS = frozenset({"conservative", "balanced", "creator_led", "audience_friendly", "custom"})
SCHEME_STATUSES = frozenset({"draft", "previewed", "partially_applied", "applied", "dismissed"})


def get_cell_value(script: dict, row_id: str, column_id: str) -> str | None:
    for row in script.get("rows", []):
        if row.get("row_id") != row_id:
            continue
        for cell in row.get("cells", []):
            if cell.get("column_id") == column_id:
                return str(cell.get("value", ""))
    return None


def find_editable_text_column(script: dict) -> dict | None:
    for column in script.get("columns", []):
        key = column.get("key", "")
        if key in {"feedback"}:
            continue
        if column.get("type") in {"text", "textarea"}:
            return column
    return None


def normalize_hunk(raw: dict[str, Any], *, script: dict) -> dict[str, Any]:
    row_id = str(raw.get("row_id", "")).strip()
    column_id = str(raw.get("column_id", "")).strip()
    removed = str(raw.get("removed", ""))
    added = str(raw.get("added", ""))
    if not row_id or not column_id:
        raise ValueError("Hunk requires row_id and column_id")
    current = get_cell_value(script, row_id, column_id)
    if current is None:
        raise ValueError(f"Cell not found for hunk: {row_id}/{column_id}")
    return {
        "hunk_id": str(raw.get("hunk_id") or new_id("hunk")),
        "row_id": row_id,
        "column_id": column_id,
        "context": str(raw.get("context", ""))[:500],
        "removed": removed if "removed" in raw else current,
        "added": added,
    }


def normalize_scheme(
    raw: dict[str, Any],
    *,
    project_id: str,
    script_version_id: str | None,
    script: dict,
) -> dict[str, Any]:
    direction = str(raw.get("direction", "balanced"))
    if direction not in SCHEME_DIRECTIONS:
        direction = "balanced"

    target_issue_ids = [str(item) for item in (raw.get("target_issue_ids") or []) if str(item).strip()]
    related_node_ids = [str(item) for item in (raw.get("related_node_ids") or []) if str(item).strip()]

    tradeoffs_raw = raw.get("tradeoffs") or {}
    if isinstance(tradeoffs_raw, dict):
        tradeoffs = {
            "brand": str(tradeoffs_raw.get("brand", ""))[:800],
            "audience": str(tradeoffs_raw.get("audience", ""))[:800],
            "creator": str(tradeoffs_raw.get("creator", ""))[:800],
        }
    else:
        tradeoffs = {"brand": "", "audience": "", "creator": ""}

    hunks: list[dict[str, Any]] = []
    for item in raw.get("hunks") or []:
        if not isinstance(item, dict):
            continue
        try:
            hunks.append(normalize_hunk(item, script=script))
        except ValueError:
            continue

    status = str(raw.get("status", "draft"))
    if status not in SCHEME_STATUSES:
        status = "draft"

    return {
        "scheme_id": str(raw.get("scheme_id") or new_id("scheme")),
        "project_id": project_id,
        "title": str(raw.get("title", "修改方案"))[:120],
        "direction": direction,
        "target_issue_ids": target_issue_ids,
        "changes_summary": str(raw.get("changes_summary", ""))[:2000],
        "rationale": str(raw.get("rationale", ""))[:2000],
        "tradeoffs": tradeoffs,
        "sacrifice": str(raw.get("sacrifice", ""))[:1000],
        "communication_scene": str(raw.get("communication_scene", ""))[:1000],
        "brand_objection": str(raw.get("brand_objection", ""))[:1000],
        "response_script": str(raw.get("response_script", ""))[:2000],
        "risk": str(raw.get("risk", ""))[:1000],
        "hunks": hunks,
        "related_node_ids": related_node_ids,
        "based_on_script_version_id": script_version_id,
        "status": status,
        "created_at": str(raw.get("created_at") or now_iso()),
    }


def validate_hunk_apply(script: dict, hunk: dict[str, Any]) -> None:
    current = get_cell_value(script, hunk["row_id"], hunk["column_id"])
    if current is None:
        raise ValueError(f"Cell not found: {hunk['row_id']}/{hunk['column_id']}")
    if current != hunk["removed"]:
        raise ValueError(
            f"Cell content changed since proposal; expected removed text mismatch "
            f"(row {hunk['row_id']})"
        )


def apply_hunk_to_script(script: dict, hunk: dict[str, Any]) -> dict:
    validate_hunk_apply(script, hunk)
    return update_cell(script, hunk["row_id"], hunk["column_id"], hunk["added"])


def merge_scheme_updates(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(existing)
    merged.update({key: value for key, value in updates.items() if value is not None})
    return merged
