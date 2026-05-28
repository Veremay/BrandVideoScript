from __future__ import annotations

import json
from typing import Any, Callable

from app.services.llm_client import LLMClient
from app.services.pipeline_log import log_llm_mock, log_step
from app.services.prompt_loader import load_prompt, render_prompt


def _agent_system_prompt(agent_file: str) -> str:
    ibis_types = load_prompt("ibis_types.md")
    template = load_prompt(agent_file)
    return render_prompt(template, {"IBIS_TYPES": ibis_types})


async def invoke_agent_json(
    *,
    agent_prompt_file: str,
    context: str,
    task_type: str,
    mock_payload: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    client = LLMClient()
    system = _agent_system_prompt(agent_prompt_file)
    user = f"根据以下上下文完成分析并输出 JSON。\n\n{context}"

    log_step(
        f"agent_llm.{agent_prompt_file}",
        phase="IN",
        task_type=task_type,
        system_prompt=system,
        user_context=context,
    )

    if client.settings.siliconflow_api_key:
        try:
            result = await client.complete_json(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                task_type=task_type,
                complexity="high",
            )
            log_step(
                f"agent_llm.{agent_prompt_file}",
                phase="OUT",
                task_type=task_type,
                source="llm",
                payload=result,
            )
            return result
        except Exception as exc:
            log_llm_mock(
                task_type,
                reason=f"LLM failed, using mock: {type(exc).__name__}: {exc!r}",
            )
            result = mock_payload()
            log_step(
                f"agent_llm.{agent_prompt_file}",
                phase="OUT",
                task_type=task_type,
                source="mock_fallback",
                payload=result,
            )
            return result

    log_llm_mock(task_type, reason="no API key")
    result = mock_payload()
    log_step(
        f"agent_llm.{agent_prompt_file}",
        phase="OUT",
        task_type=task_type,
        source="mock_no_key",
        payload=result,
    )
    return result


def existing_nodes_summary(project: dict[str, Any], limit: int = 24) -> str:
    lines: list[str] = []
    for node in project.get("rationale_nodes", [])[:limit]:
        lines.append(
            f"- id={node.get('node_id')} type={node.get('node_type')} "
            f"source={node.get('source_type')} title={str(node.get('title', ''))[:50]}"
        )
    return "\n".join(lines) if lines else "（无）"


def script_excerpt_for_rows(project: dict[str, Any], row_ids: set[str]) -> str:
    script = project.get("current_script") or {}
    parts: list[str] = []
    for row in script.get("rows", []):
        if row.get("row_id") not in row_ids:
            continue
        for cell in row.get("cells", []):
            value = str(cell.get("value", "")).strip()
            if value:
                parts.append(value)
    return " | ".join(parts)[:800]


def format_script_for_prompt(project: dict[str, Any]) -> str:
    """Full script table for LLM prompts (row_id + column_id + keys, not a truncated excerpt)."""
    script = project.get("current_script") or {}
    columns = sorted(script.get("columns", []), key=lambda item: item.get("order", 0))
    rows = sorted(script.get("rows", []), key=lambda item: item.get("order", 0))
    if not rows:
        return "（无脚本行）"

    col_by_id = {str(column.get("column_id", "")): column for column in columns}
    lines: list[str] = [
        "列定义（hunk 必须使用 column_id，可参考 key/label）：",
        *[
            f"- column_id={column.get('column_id')} key={column.get('key')} label={column.get('label')}"
            for column in columns
            if column.get("key") != "feedback"
        ],
        "",
        "脚本全文：",
    ]

    for index, row in enumerate(rows, start=1):
        row_id = str(row.get("row_id", ""))
        cells = {str(cell.get("column_id", "")): str(cell.get("value", "")) for cell in row.get("cells", [])}
        lines.append(f"### 第 {index} 行 row_id={row_id}")
        for column in columns:
            key = str(column.get("key", ""))
            if key == "feedback":
                continue
            column_id = str(column.get("column_id", ""))
            label = str(column.get("label", key))
            value = cells.get(column_id, "").strip()
            if not value:
                continue
            lines.append(f"- {label} (column_id={column_id}, key={key}): {value}")
        lines.append("")

    return "\n".join(lines).strip()


def format_quotes(quotes: list[dict[str, Any]] | None) -> str:
    if not quotes:
        return ""
    return "\n".join(f'- "{q.get("text", "")[:300]}" row={q.get("row_id", "")}' for q in quotes)


def perspective_result_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)[:2000]
