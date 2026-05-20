"""Parse Expert Agent's `<expert_suggestions>` artifact block.

Each item is a multi-field suggestion with one or more cell-level hunks. We
validate hunks against the caller's `allowed_cells` so the model cannot
fabricate row/column ids or `old` values that drift from the live script.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from app.repositories.projects import EXPERT_DIRECTIONS


MARKER_START = "<expert_suggestions>"
MARKER_END = "</expert_suggestions>"

# Tolerant: accept singular `expert_suggestion`, `expert_suggestions`, and the
# longer `expert_suggestion_proposals` spelling that LLMs occasionally drift to.
_OPEN_RE = re.compile(r"<expert_suggestions?(?:_proposals)?>", re.IGNORECASE)
_CLOSE_RE = re.compile(r"</expert_suggestions?(?:_proposals)?>", re.IGNORECASE)

MAX_MARKER_LEN = len("</expert_suggestion_proposals>")

MAX_TITLE = 120
MAX_DESCRIPTION = 600
MAX_RATIONALE = 800
MAX_TRADEOFF = 600
MAX_RISK = 400
MAX_TARGET_PROBLEM = 400
MAX_EXPLANATION = 800
MAX_REASON = 280

MAX_ITEMS = 3
MAX_HUNKS_PER_ITEM = 6


def find_marker_start(text: str) -> int:
    m = _OPEN_RE.search(text)
    return m.start() if m else -1


def _locate_block(text: str) -> tuple[int, int, int] | None:
    open_m = _OPEN_RE.search(text)
    if not open_m:
        return None
    body_start = open_m.end()
    close_m = _CLOSE_RE.search(text, body_start)
    if close_m:
        return open_m.start(), body_start, close_m.start()
    return open_m.start(), body_start, len(text)


def strip_proposal_block(text: str) -> str:
    located = _locate_block(text)
    if located is None:
        return text
    open_start, _body_start, body_end = located
    close_m = _CLOSE_RE.search(text, body_end - 1) if body_end < len(text) else None
    end_pos = close_m.end() if close_m else len(text)
    cleaned = text[:open_start] + text[end_pos:]
    return cleaned.rstrip()


def _truncate(value: object, *, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _normalize_hunk(
    hunk: object,
    *,
    allowed_cells: dict[tuple[str, str], str],
    forbidden_columns: set[str],
) -> dict[str, Any] | None:
    if not isinstance(hunk, dict):
        return None
    row_id = str(hunk.get("row_id") or "").strip()
    column_id = str(hunk.get("column_id") or "").strip()
    if not row_id or not column_id:
        return None
    if column_id in forbidden_columns:
        return None

    expected_value = allowed_cells.get((row_id, column_id))
    if expected_value is None:
        return None

    old_text = hunk.get("old")
    new_text = hunk.get("new")
    if old_text is None or new_text is None:
        return None
    old_text = str(old_text)
    new_text = str(new_text)
    if old_text != expected_value:
        return None
    if old_text == new_text:
        return None

    reason = _truncate(hunk.get("reason"), limit=MAX_REASON)
    return {
        "row_id": row_id,
        "column_id": column_id,
        "old": old_text,
        "new": new_text,
        "reason": reason,
    }


def _normalize_suggestion(
    item: object,
    *,
    allowed_cells: dict[tuple[str, str], str],
    forbidden_columns: set[str],
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    title = _truncate(item.get("title"), limit=MAX_TITLE)
    if not title:
        return None

    direction = str(item.get("direction") or "").strip().lower()
    if direction not in EXPERT_DIRECTIONS:
        direction = "custom"

    hunks_raw = item.get("hunks") or []
    if not isinstance(hunks_raw, list):
        return None

    hunks: list[dict[str, Any]] = []
    for raw in hunks_raw[: MAX_HUNKS_PER_ITEM * 2]:
        normalized = _normalize_hunk(raw, allowed_cells=allowed_cells, forbidden_columns=forbidden_columns)
        if normalized is None:
            continue
        hunks.append(normalized)
        if len(hunks) >= MAX_HUNKS_PER_ITEM:
            break

    if not hunks:
        return None

    return {
        "title": title,
        "direction": direction,
        "description": _truncate(item.get("description"), limit=MAX_DESCRIPTION),
        "target_problem": _truncate(item.get("target_problem"), limit=MAX_TARGET_PROBLEM),
        "rationale": _truncate(item.get("rationale"), limit=MAX_RATIONALE),
        "brand_tradeoff": _truncate(item.get("brand_tradeoff"), limit=MAX_TRADEOFF),
        "audience_tradeoff": _truncate(item.get("audience_tradeoff"), limit=MAX_TRADEOFF),
        "creator_tradeoff": _truncate(item.get("creator_tradeoff"), limit=MAX_TRADEOFF),
        "risk": _truncate(item.get("risk"), limit=MAX_RISK),
        "explanation_to_brand": _truncate(item.get("explanation_to_brand"), limit=MAX_EXPLANATION),
        "hunks": hunks,
    }


def parse_suggestion_items(
    text: str,
    *,
    allowed_cells: dict[tuple[str, str], str],
    forbidden_columns: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    located = _locate_block(text)
    if located is None:
        return []
    _open_start, body_start, body_end = located
    raw = text[body_start:body_end].strip()

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()

    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []

    items_raw = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items_raw, list):
        return []

    forbidden = set(forbidden_columns or ())
    out: list[dict[str, Any]] = []
    for item in items_raw[: MAX_ITEMS * 2]:
        normalized = _normalize_suggestion(item, allowed_cells=allowed_cells, forbidden_columns=forbidden)
        if normalized is None:
            continue
        out.append(normalized)
        if len(out) >= MAX_ITEMS:
            break
    return out
