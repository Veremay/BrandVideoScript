from typing import Any


def summarize_script(script: dict[str, Any], max_rows: int = 12) -> str:
    columns = {column.get("column_id"): column.get("label", column.get("column_id", "")) for column in script.get("columns", [])}
    lines: list[str] = []
    for row in script.get("rows", [])[:max_rows]:
        cell_parts = []
        for cell in row.get("cells", []):
            label = columns.get(cell.get("column_id"), cell.get("column_id", ""))
            value = str(cell.get("value", "")).strip()
            if value:
                cell_parts.append(f"{label}: {value}")
        if cell_parts:
            lines.append(f"{row.get('row_id')}: " + " | ".join(cell_parts))
    return "\n".join(lines) if lines else "当前脚本为空。"


def format_quotes(quotes: list[dict[str, Any]]) -> str:
    if not quotes:
        return "无。"

    lines = []
    for quote in quotes:
        location = " / ".join(str(quote.get(key, "")) for key in ["row_id", "column_id"] if quote.get(key))
        prefix = f"[{location}] " if location else ""
        lines.append(f"- {prefix}{quote.get('text', '')}")
    return "\n".join(lines)


def format_recent_messages(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "无。"
    return "\n".join(f"{message.get('role')}: {message.get('content')}" for message in messages)


def format_brand_research(project: dict[str, Any]) -> tuple[str, str]:
    br = project.get("brand_research") or {}
    summary = (br.get("research_summary") or "").strip() or "（暂无品牌检索摘要。上传 Brief 后将自动检索内部手册与公开来源。）"
    lines: list[str] = []
    for item in (br.get("wiki_snippets") or [])[:6]:
        heading = item.get("heading") or ""
        snippet = (item.get("snippet") or "")[:500]
        path = item.get("path") or ""
        lines.append(f"[品牌手册 {path}] {heading}\n{snippet}")
    for item in (br.get("web_snippets") or [])[:5]:
        title = item.get("title") or ""
        url = item.get("url") or ""
        snippet = (item.get("snippet") or "")[:400]
        lines.append(f"[网页] {title} {url}\n{snippet}")
    snippets = "\n".join(lines) if lines else "（尚无检索片段。）"
    return summary, snippets


def find_active_persona(project: dict[str, Any]) -> str:
    active_id = project.get("active_persona_id")
    for persona in project.get("personas", []):
        if persona.get("persona_id") == active_id:
            return str(persona)
    return "未选择 persona。"


def build_prompt_variables(project: dict[str, Any], recent_messages: list[dict[str, Any]], quotes: list[dict[str, Any]]) -> dict[str, str]:
    research_summary, research_snippets = format_brand_research(project)
    return {
        "brief_summary": project.get("brief", {}).get("summary") or "无。",
        "script_summary": summarize_script(project.get("current_script", {})),
        "recent_messages": format_recent_messages(recent_messages),
        "quotes": format_quotes(quotes),
        "active_persona": find_active_persona(project),
        "brand_insights": str(project.get("brand_insights") or []),
        "audience_analysis": str(project.get("audience_analysis") or {}),
        "brand_research_summary": research_summary,
        "brand_research_snippets": research_snippets,
    }


def build_agent_chat_messages(
    *,
    agent_type: str,
    system_prompt: str,
    project: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    user_message: str,
    quotes: list[dict[str, Any]],
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]
    for message in recent_messages:
        role = message.get("role")
        if role in {"user", "assistant"} and message.get("content"):
            messages.append({"role": role, "content": message["content"]})

    quote_block = format_quotes(quotes)
    messages.append({"role": "user", "content": f"用户引用：\n{quote_block}\n\n用户问题：\n{user_message}"})
    return messages
