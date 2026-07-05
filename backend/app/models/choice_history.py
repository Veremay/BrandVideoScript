from __future__ import annotations

from typing import Any

from app.models.script import now_iso


def _as_list(value: Any) -> list[dict[str, Any]]:
    return list(value) if isinstance(value, list) else []


def _position_entry(node: dict[str, Any], *, now: str) -> dict[str, Any]:
    return {
        "position_id": str(node.get("node_id") or ""),
        "first_considered_at": now,
        "last_considered_at": now,
        "last_used_for_scheme_at": None,
        "used_scheme_ids": [],
        "status_at_use": str(node.get("lifecycle") or node.get("status") or "active"),
        "title_snapshot": str(node.get("title") or "")[:240],
        "content_snapshot": str(node.get("content") or "")[:1000],
        "source_type": str(node.get("source_type") or ""),
        "source_perspective": str(node.get("source_perspective") or ""),
    }


def record_considered_position(
    history: dict[str, Any] | None,
    node: dict[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or now_iso()
    position_id = str(node.get("node_id") or "")
    if not position_id:
        return normalize_choice_history(history)

    next_history = normalize_choice_history(history)
    positions = next_history["adopted_positions"]
    for item in positions:
        if item.get("position_id") != position_id:
            continue
        item["last_considered_at"] = timestamp
        item["status_at_use"] = str(node.get("lifecycle") or node.get("status") or item.get("status_at_use") or "active")
        item["title_snapshot"] = str(node.get("title") or item.get("title_snapshot") or "")[:240]
        item["content_snapshot"] = str(node.get("content") or item.get("content_snapshot") or "")[:1000]
        item["source_type"] = str(node.get("source_type") or item.get("source_type") or "")
        item["source_perspective"] = str(node.get("source_perspective") or item.get("source_perspective") or "")
        item.setdefault("used_scheme_ids", [])
        item.setdefault("first_considered_at", timestamp)
        item.setdefault("last_used_for_scheme_at", None)
        return next_history

    positions.append(_position_entry(node, now=timestamp))
    return next_history


def record_scheme_position_usage(
    history: dict[str, Any] | None,
    scheme: dict[str, Any],
    *,
    nodes_by_id: dict[str, dict[str, Any]] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or str(scheme.get("created_at") or now_iso())
    scheme_id = str(scheme.get("scheme_id") or "")
    target_position_ids = [
        str(item)
        for item in (scheme.get("target_position_ids") or [])
        if str(item).strip()
    ]
    next_history = normalize_choice_history(history)
    if not scheme_id or not target_position_ids:
        return next_history

    nodes_by_id = nodes_by_id or {}
    links = next_history["scheme_position_links"]
    if not any(item.get("scheme_id") == scheme_id for item in links):
        links.append(
            {
                "scheme_id": scheme_id,
                "title": str(scheme.get("title") or "")[:240],
                "direction": str(scheme.get("direction") or ""),
                "target_position_ids": target_position_ids,
                "created_at": timestamp,
            }
        )

    for position_id in target_position_ids:
        node = nodes_by_id.get(position_id) or {"node_id": position_id}
        next_history = record_considered_position(next_history, node, now=timestamp)
        for item in next_history["adopted_positions"]:
            if item.get("position_id") != position_id:
                continue
            used_scheme_ids = list(item.get("used_scheme_ids") or [])
            if scheme_id not in used_scheme_ids:
                used_scheme_ids.append(scheme_id)
            item["used_scheme_ids"] = used_scheme_ids
            item["last_used_for_scheme_at"] = timestamp
            break

    return next_history


def normalize_choice_history(history: dict[str, Any] | None) -> dict[str, Any]:
    source = history if isinstance(history, dict) else {}
    return {
        "adopted_positions": _as_list(source.get("adopted_positions")),
        "scheme_position_links": _as_list(source.get("scheme_position_links")),
    }


def format_choice_history_for_prompt(history: dict[str, Any] | None) -> str:
    normalized = normalize_choice_history(history)
    positions = normalized["adopted_positions"]
    links = normalized["scheme_position_links"]
    if not positions and not links:
        return "(no historical creator choice trajectory recorded yet)"

    lines: list[str] = []
    if positions:
        lines.append("Adopted / used positions:")
        for item in positions[:30]:
            scheme_ids = ", ".join(str(sid) for sid in (item.get("used_scheme_ids") or [])) or "none"
            lines.append(
                "- "
                f"position_id={item.get('position_id')} | "
                f"title={item.get('title_snapshot', '')} | "
                f"content={str(item.get('content_snapshot', ''))[:220]} | "
                f"used_scheme_ids={scheme_ids} | "
                f"last_used_for_scheme_at={item.get('last_used_for_scheme_at') or ''}"
            )

    if links:
        lines.append("Generated scheme links:")
        for item in links[-20:]:
            target_ids = ", ".join(str(pid) for pid in (item.get("target_position_ids") or []))
            lines.append(
                "- "
                f"scheme_id={item.get('scheme_id')} | "
                f"title={item.get('title', '')} | "
                f"direction={item.get('direction', '')} | "
                f"target_position_ids={target_ids}"
            )
    return "\n".join(lines)
