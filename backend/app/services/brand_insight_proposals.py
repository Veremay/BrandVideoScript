"""Parse Brand Agent's `<brand_insight_proposals>` artifact block from assistant turn.

Tolerant to common LLM typos:
- both `insight` and `insights` spellings
- missing or malformed closing tag (we strip from open marker to end of string)
"""

from __future__ import annotations

import json
import re
from typing import Any

# Canonical marker strings (used by streaming code to size the look-back buffer).
MARKER_START = "<brand_insight_proposals>"
MARKER_END = "</brand_insight_proposals>"

# Tolerant variants — accept singular / plural spellings and any case.
_OPEN_RE = re.compile(r"<brand_insights?_proposals>", re.IGNORECASE)
_CLOSE_RE = re.compile(r"</brand_insights?_proposals>", re.IGNORECASE)
# Longest possible literal marker prefix the streaming layer might encounter.
MAX_MARKER_LEN = len("<brand_insights_proposals>")

ALLOWED_CATEGORIES = {"explicit_requirement", "implicit_requirement", "brand_feedback"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_SOURCE_TYPES = {"brief", "brand_wiki", "web", "pr_feedback", "script", "chat"}


def find_marker_start(text: str) -> int:
    """Return start index of the opening proposal marker (any tolerated spelling), or -1."""
    m = _OPEN_RE.search(text)
    return m.start() if m else -1


def _locate_block(text: str) -> tuple[int, int, int] | None:
    """Return (open_start, body_start, body_end_excl) or None.

    When the closing marker is missing/malformed, body extends to end of string;
    open_end is excluded from body, close_end is the slice position used for stripping.
    """
    open_m = _OPEN_RE.search(text)
    if not open_m:
        return None
    body_start = open_m.end()
    close_m = _CLOSE_RE.search(text, body_start)
    if close_m:
        return open_m.start(), body_start, close_m.start()
    return open_m.start(), body_start, len(text)


def strip_proposal_block(text: str) -> str:
    """Remove the proposal block from assistant text.

    Tolerates missing / mistyped closing tags by stripping from the open marker to
    the matching close marker if found, else to end of string.
    """
    located = _locate_block(text)
    if located is None:
        return text
    open_start, _body_start, body_end = located
    close_m = _CLOSE_RE.search(text, body_end - 1) if body_end < len(text) else None
    end_pos = close_m.end() if close_m else len(text)
    cleaned = text[:open_start] + text[end_pos:]
    return cleaned.rstrip()


def parse_proposal_items(text: str) -> list[dict[str, Any]]:
    """Find the marker block and return validated proposal items. Empty list when no block / parse fails."""
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

    out: list[dict[str, Any]] = []
    for item in items_raw[:8]:
        if not isinstance(item, dict):
            continue
        category = item.get("category")
        if category not in ALLOWED_CATEGORIES:
            continue
        title = str(item.get("title") or "").strip()[:120]
        content = str(item.get("content") or "").strip()
        if not title or not content:
            continue
        reason = str(item.get("reason") or "").strip()[:600]
        confidence = item.get("confidence") or "medium"
        if confidence not in ALLOWED_CONFIDENCE:
            confidence = "medium"

        evidence_raw = item.get("evidence") or []
        evidence: list[dict[str, Any]] = []
        if isinstance(evidence_raw, list):
            for ev in evidence_raw[:6]:
                if not isinstance(ev, dict):
                    continue
                source_type = ev.get("source_type") or "chat"
                if source_type not in ALLOWED_SOURCE_TYPES:
                    source_type = "chat"
                quote = str(ev.get("quote") or "").strip()[:500]
                if not quote:
                    continue
                evidence.append({"source_type": source_type, "quote": quote})

        out.append(
            {
                "category": category,
                "title": title,
                "content": content[:1000],
                "reason": reason,
                "confidence": confidence,
                "evidence": evidence,
            }
        )
    return out
