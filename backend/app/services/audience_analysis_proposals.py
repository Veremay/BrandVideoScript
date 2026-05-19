"""Parse Audience Agent's `<audience_analysis>` artifact block.

Mirror of `brand_insight_proposals` but for a single structured analysis object
(not a list of items). Tolerant to common LLM typos:
- singular `<audience_analyse>` / `<audience_analyses>` spellings
- missing closing tag (strip from open marker to end of string)
"""

from __future__ import annotations

import json
import re
from typing import Any

MARKER_START = "<audience_analysis>"
MARKER_END = "</audience_analysis>"

# Tolerant: accept analysis / analyses / analyse spellings, any case.
_OPEN_RE = re.compile(r"<audience_analy(?:sis|ses|se)>", re.IGNORECASE)
_CLOSE_RE = re.compile(r"</audience_analy(?:sis|ses|se)>", re.IGNORECASE)

MAX_MARKER_LEN = len("</audience_analyses>")

MAX_LIST_LEN = 6
MAX_REASON_CHARS = 280
MAX_TEXT_CHARS = 600


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


def _coerce_score(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        score = value
    elif isinstance(value, float):
        score = int(value)
    elif isinstance(value, str):
        try:
            score = int(value.strip())
        except (TypeError, ValueError):
            return None
    else:
        return None
    if 1 <= score <= 5:
        return score
    return None


def _coerce_str_list(value: object, *, limit: int = MAX_LIST_LEN, max_chars: int = MAX_TEXT_CHARS) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for entry in value:
        if entry is None:
            continue
        text = str(entry).strip()
        if text:
            out.append(text[:max_chars])
        if len(out) >= limit:
            break
    return out


def _coerce_row_parts(value: object, allowed_row_ids: set[str]) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        row_id = str(entry.get("row_id") or "").strip()
        if not row_id:
            continue
        if allowed_row_ids and row_id not in allowed_row_ids:
            continue
        reason = str(entry.get("reason") or "").strip()[:MAX_REASON_CHARS]
        out.append({"row_id": row_id, "reason": reason})
        if len(out) >= MAX_LIST_LEN:
            break
    return out


def parse_analysis_payload(text: str, *, allowed_row_ids: set[str] | None = None) -> dict[str, Any] | None:
    """Return validated analysis dict (excluding persona / timestamps) or None on failure."""
    located = _locate_block(text)
    if located is None:
        return None
    _open_start, body_start, body_end = located
    raw = text[body_start:body_end].strip()

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    summary = str(data.get("summary") or "").strip()[:MAX_TEXT_CHARS]
    allowed = allowed_row_ids or set()
    analysis = {
        "summary": summary,
        "naturalness_score": _coerce_score(data.get("naturalness_score")),
        "credibility_score": _coerce_score(data.get("credibility_score")),
        "ad_sensitivity_score": _coerce_score(data.get("ad_sensitivity_score")),
        "key_risks": _coerce_str_list(data.get("key_risks")),
        "liked_parts": _coerce_row_parts(data.get("liked_parts"), allowed),
        "rejected_parts": _coerce_row_parts(data.get("rejected_parts"), allowed),
        "suggestions": _coerce_str_list(data.get("suggestions")),
    }

    informative = any(
        analysis[key] is not None for key in ("naturalness_score", "credibility_score", "ad_sensitivity_score")
    ) or analysis["summary"] or analysis["key_risks"] or analysis["liked_parts"] or analysis["rejected_parts"] or analysis["suggestions"]
    if not informative:
        return None
    return analysis
