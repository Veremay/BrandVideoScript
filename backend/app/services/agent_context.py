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


_CATEGORY_LABEL = {
    "explicit_requirement": "显式需求",
    "implicit_requirement": "隐式需求",
    "brand_feedback": "品牌反馈",
}


def format_brand_entity(project: dict[str, Any]) -> str:
    br = project.get("brand_research") or {}
    entity = br.get("entity") or {}
    brand_name = (entity.get("brand_name") or "").strip()
    if not brand_name:
        return "（尚未识别合作品牌。）"
    parts = [f"品牌：{brand_name}"]
    category = (entity.get("category") or "").strip()
    if category:
        parts.append(f"品类：{category}")
    product = (entity.get("product") or "").strip()
    if product:
        parts.append(f"主推产品：{product}")
    if br.get("matched_wiki"):
        parts.append("内部手册：已匹配")
    return " | ".join(parts)


def format_brand_insights(project: dict[str, Any], *, max_per_category: int = 6) -> str:
    insights = project.get("brand_insights") or []
    if not insights:
        return "（尚未沉淀品牌洞察。上传 Brief 后将自动生成显式 / 隐式需求。）"

    grouped: dict[str, list[dict[str, Any]]] = {
        "explicit_requirement": [],
        "implicit_requirement": [],
        "brand_feedback": [],
    }
    for item in insights:
        cat = item.get("category")
        if cat in grouped:
            grouped[cat].append(item)

    sections: list[str] = []
    for cat, items in grouped.items():
        if not items:
            continue
        sections.append(f"### {_CATEGORY_LABEL[cat]}（{len(items)} 条）")
        for ins in items[:max_per_category]:
            title = (ins.get("title") or "").strip() or "(无标题)"
            content = (ins.get("content") or "").strip()
            reason = (ins.get("reason") or "").strip()
            conf = ins.get("confidence") or "medium"
            status = ins.get("status") or "new"
            origin = "用户" if ins.get("created_by") == "user" else "Agent"
            ev_lines: list[str] = []
            for ev in (ins.get("evidence") or [])[:3]:
                source = ev.get("source_type") or "brief"
                quote = (ev.get("quote") or "").strip()[:160]
                if quote:
                    ev_lines.append(f"  - [{source}] {quote}")
            evidence_block = "\n".join(ev_lines) if ev_lines else "  - （无依据）"
            sections.append(
                f"- **{title}**（{origin} · {conf} · {status}）\n"
                f"  {content}\n"
                f"  推理：{reason or '（无）'}\n"
                f"  依据：\n{evidence_block}"
            )
    return "\n".join(sections) if sections else "（暂无可用洞察。）"


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
        "brand_entity": format_brand_entity(project),
        "brand_insights": format_brand_insights(project),
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
