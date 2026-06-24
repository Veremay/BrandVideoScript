from __future__ import annotations

from typing import Any, Literal

AgentRole = Literal["brand", "audience", "expert", "coordinator"]

FORBIDDEN_KEYS: dict[AgentRole, set[str]] = {
    "brand": {
        "personas",
        "active_persona_id",
        "audience_perspective_result",
        "audience_analysis",
    },
    "audience": {
        "brief",
        "brand_insights",
        "brand_perspective_result",
    },
    "expert": set(),
    "coordinator": set(),
}


def build_agent_context(role: AgentRole, project: dict[str, Any]) -> dict[str, Any]:
    """Whitelist project fields per agent role (context isolation)."""
    if role == "brand":
        return {
            "project_id": project.get("_id"),
            "platform_context": project.get("platform_context", "other"),
            "brief": project.get("brief", {}),
            # Existing requirements from a previous parse, used when brief is already parsed.
            "brand_perspective_result": project.get("brand_perspective_result") or {},
            "brand_insights": project.get("brand_insights", []),
            "brand_feedback_rows": _feedback_rows(project),
            "current_script_version_id": project.get("current_script_version_id"),
            "script_excerpt": _script_excerpt(project),
        }
    if role == "audience":
        active = _active_persona(project)
        return {
            "project_id": project.get("_id"),
            "platform_context": project.get("platform_context", "other"),
            "active_persona": active,
            "current_script_version_id": project.get("current_script_version_id"),
            "script_excerpt": _script_excerpt(project),
        }
    if role == "expert":
        return {
            "project_id": project.get("_id"),
            "platform_context": project.get("platform_context", "other"),
            "brief_text": str((project.get("brief") or {}).get("text") or "").strip(),
            "brand_perspective_result": project.get("brand_perspective_result") or {},
            "brand_insights": project.get("brand_insights", []),
            "audience_perspective_result": project.get("audience_perspective_result") or {},
            "rationale_graph_summary": _graph_summary(project),
            "current_script_version_id": project.get("current_script_version_id"),
            "script_excerpt": _script_excerpt(project),
        }
    return dict(project)


def assert_context_isolation(role: AgentRole, context: dict[str, Any]) -> None:
    forbidden = FORBIDDEN_KEYS.get(role, set())
    leaked = forbidden.intersection(context.keys())
    if leaked:
        raise ValueError(f"Context isolation violation for {role}: {sorted(leaked)}")


def _active_persona(project: dict[str, Any]) -> dict[str, Any] | None:
    active_id = project.get("active_persona_id")
    if not active_id:
        return None
    for persona in project.get("personas", []):
        if persona.get("persona_id") == active_id:
            return persona
    return None


def _feedback_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    script = project.get("current_script") or {}
    feedback_col = next((c for c in script.get("columns", []) if c.get("key") == "feedback"), None)
    if not feedback_col:
        return rows
    col_id = feedback_col["column_id"]
    for row in script.get("rows", []):
        value = next((cell.get("value", "") for cell in row.get("cells", []) if cell.get("column_id") == col_id), "")
        if value.strip():
            rows.append({"row_id": row.get("row_id", ""), "feedback": value.strip()})
    return rows


def _script_excerpt(project: dict[str, Any], max_chars: int = 800) -> str:
    script = project.get("current_script") or {}
    parts: list[str] = []
    for row in script.get("rows", [])[:8]:
        for cell in row.get("cells", []):
            value = str(cell.get("value", "")).strip()
            if value:
                parts.append(value)
    text = " | ".join(parts)
    return text[:max_chars]


def _graph_summary(project: dict[str, Any], limit: int = 12) -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    for node in project.get("rationale_nodes", [])[:limit]:
        summary.append(
            {
                "node_id": node.get("node_id", ""),
                "node_type": node.get("node_type", ""),
                "title": node.get("title", ""),
                "source_type": node.get("source_type", ""),
            }
        )
    return summary
