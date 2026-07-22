from __future__ import annotations

import re
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any

from app.models.script import new_id, now_iso
from app.models.script_ops import update_cell

SCHEME_DIRECTIONS = frozenset({"conservative", "balanced", "creator_led", "audience_friendly", "custom"})
SCHEME_STATUSES = frozenset({"draft", "previewed", "partially_applied", "applied", "dismissed"})


def _normalize_cell_text(value: str) -> str:
    """Collapse whitespace so LLM / editor drift does not block apply."""
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _texts_compatible(removed: str, current: str) -> bool:
    if removed == current:
        return True
    if not removed or not current:
        return False
    norm_removed = _normalize_cell_text(removed)
    norm_current = _normalize_cell_text(current)
    if not norm_removed or not norm_current:
        return False
    if norm_removed == norm_current:
        return True
    if norm_removed in norm_current or norm_current in norm_removed:
        return True
    if norm_current.startswith(norm_removed[:80]) or norm_removed.startswith(norm_current[:80]):
        return True
    return SequenceMatcher(None, norm_removed, norm_current).ratio() >= 0.55


def _columns_by_key(script: dict) -> dict[str, dict]:
    return {str(column.get("key", "")): column for column in script.get("columns", []) if column.get("key")}


def _columns_by_id(script: dict) -> dict[str, dict]:
    return {str(column.get("column_id", "")): column for column in script.get("columns", []) if column.get("column_id")}


def _sorted_rows(script: dict) -> list[dict]:
    return sorted(script.get("rows", []), key=lambda row: row.get("order", 0))


def resolve_hunk_identifiers(script: dict, raw: dict[str, Any]) -> dict[str, Any] | None:
    """Map LLM row/column aliases (keys, row order, removed-text match) to real script ids."""
    resolved = dict(raw)
    columns_by_id = _columns_by_id(script)
    columns_by_key = _columns_by_key(script)

    column_ref = str(resolved.get("column_id", "")).strip()
    column: dict | None = columns_by_id.get(column_ref)
    if column is None and column_ref:
        column = columns_by_key.get(column_ref)
    if column is None and column_ref:
        lowered = column_ref.lower()
        for item in script.get("columns", []):
            label = str(item.get("label", "")).lower()
            key = str(item.get("key", "")).lower()
            if lowered in {label, key}:
                column = item
                break
    if column is None:
        return None
    resolved["column_id"] = str(column["column_id"])

    row_ref = str(resolved.get("row_id", "")).strip()
    rows = _sorted_rows(script)
    row: dict | None = next((item for item in rows if item.get("row_id") == row_ref), None)

    if row is None and row_ref.isdigit():
        order = int(row_ref)
        if 1 <= order <= len(rows):
            row = rows[order - 1]

    removed_hint = str(resolved.get("removed", "")).strip()

    def _text_matches(current: str) -> bool:
        if not current or not removed_hint:
            return False
        return removed_hint == current or removed_hint in current or current in removed_hint

    if row is None and removed_hint:
        matches: list[dict] = []
        column_id = str(column["column_id"])
        for candidate in rows:
            current = get_cell_value(script, str(candidate.get("row_id", "")), column_id) or ""
            if _text_matches(current):
                matches.append(candidate)
        if len(matches) == 1:
            row = matches[0]

    if row is None and removed_hint:
        for candidate in rows:
            for item in script.get("columns", []):
                if str(item.get("key", "")) == "feedback":
                    continue
                column_id = str(item.get("column_id", ""))
                current = get_cell_value(script, str(candidate.get("row_id", "")), column_id) or ""
                if _text_matches(current):
                    row = candidate
                    column = item
                    resolved["column_id"] = column_id
                    break
            if row is not None:
                break

    if row is None:
        return None

    resolved["row_id"] = str(row["row_id"])
    column_id = str(column["column_id"])
    current = get_cell_value(script, resolved["row_id"], column_id) or ""
    if removed_hint and current and removed_hint != current:
        if removed_hint in current or current.startswith(removed_hint[:80]):
            resolved["removed"] = current
    elif "removed" not in raw and current:
        resolved["removed"] = current

    return resolved


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
    added = str(raw.get("added", ""))
    if not row_id or not column_id:
        raise ValueError("Hunk requires row_id and column_id")
    current = get_cell_value(script, row_id, column_id)
    if current is None:
        raise ValueError(f"Cell not found for hunk: {row_id}/{column_id}")
    decision = str(raw.get("decision", "pending"))
    if decision not in {"pending", "accepted", "rejected"}:
        decision = "pending"

    applied_at = raw.get("applied_at")
    # Hunks replace the whole cell; anchor removed to the live value so apply-guards stay valid.
    return {
        "hunk_id": str(raw.get("hunk_id") or new_id("hunk")),
        "row_id": row_id,
        "column_id": column_id,
        "context": str(raw.get("context", ""))[:500],
        "removed": current,
        "added": added,
        "decision": decision,
        "applied_at": str(applied_at) if applied_at else None,
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
    target_position_ids = [str(item) for item in (raw.get("target_position_ids") or []) if str(item).strip()]
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
        resolved = resolve_hunk_identifiers(script, item)
        if resolved is None:
            continue
        try:
            hunks.append(normalize_hunk(resolved, script=script))
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
        "target_position_ids": target_position_ids,
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


def reconcile_hunk_for_apply(script: dict, hunk: dict[str, Any]) -> dict[str, Any]:
    """Align hunk.removed with live cell text when the script drifted slightly after the plan was generated."""
    current = get_cell_value(script, hunk["row_id"], hunk["column_id"])
    if current is None:
        raise ValueError(f"Cell not found: {hunk['row_id']}/{hunk['column_id']}")
    removed = str(hunk.get("removed", ""))
    added = str(hunk.get("added", ""))
    if current == removed:
        return hunk
    # Already applied (e.g. retry / duplicate hunk on same cell).
    if current == added or _normalize_cell_text(current) == _normalize_cell_text(added):
        return {**hunk, "removed": current}
    if _texts_compatible(removed, current):
        return {**hunk, "removed": current}
    # Full-cell replace: accept overwrites the live cell once the user confirms the hunk.
    return {**hunk, "removed": current}


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
