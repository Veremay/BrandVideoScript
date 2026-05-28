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


def format_quotes(quotes: list[dict[str, Any]] | None) -> str:
    if not quotes:
        return ""
    return "\n".join(f'- "{q.get("text", "")[:300]}" row={q.get("row_id", "")}' for q in quotes)


def perspective_result_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)[:2000]
