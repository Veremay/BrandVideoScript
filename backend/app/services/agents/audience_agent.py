from __future__ import annotations

from typing import Any

from app.services.agent_context import assert_context_isolation, build_agent_context
from app.services.agent_llm import (
    existing_nodes_summary,
    format_quotes,
    invoke_agent_json,
    script_excerpt_for_rows,
)
from app.services.pipeline_log import log_step
from app.services.tools.ibis_graph import persist_rationale_graph

AUDIENCE_SOURCES = {"audience_persona", "audience_simulation"}


async def run_audience_agent(
    project: dict[str, Any],
    *,
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
) -> dict[str, Any]:
    context = build_agent_context("audience", project)
    assert_context_isolation("audience", context)

    persona = context.get("active_persona")
    if not persona:
        raise ValueError("Active persona is required for audience analysis")

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")

    row_ids = set(changed_row_ids or [])
    if quotes:
        for q in quotes:
            if q.get("row_id"):
                row_ids.add(str(q["row_id"]))

    log_step(
        "audience_agent",
        phase="IN",
        project_id=project_id,
        persona_id=persona.get("persona_id"),
        quotes=quotes,
        changed_row_ids=sorted(row_ids),
    )

    context_block = "\n\n".join(
        [
            f"## Persona\n{persona}",
            f"## 平台\n{context.get('platform_context', 'other')}",
            f"## 脚本摘要\n{context.get('script_excerpt', '')}",
            f"## 变动/选段脚本\n{script_excerpt_for_rows(project, row_ids) if row_ids else ''}",
            f"## Quotes\n{format_quotes(quotes)}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        return {
            "naturalness": f"以 {persona.get('name')} 视角评估",
            "ad_sense": "需降低硬广感",
            "trust": "、".join(persona.get("trust_trigger") or []) or "真实体验",
            "drop_off_risk": "、".join(persona.get("reject_trigger") or []) or "硬广话术",
            "suggestions": ["开头点明观众价值"],
            "structured_issues": [{"title": "广告感风险", "content": "Persona 对广告较敏感"}],
            "ibis": {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "降低广告感优先",
                        "content": "结合 Persona 广告敏感度，内容应自然、弱化硬广话术。",
                        "source_type": "audience_simulation",
                        "source_perspective": "audience",
                    }
                ],
                "edges": [],
            },
        }

    payload = await invoke_agent_json(
        agent_prompt_file="audience_agent.md",
        context=context_block,
        task_type="audience_analyze_script",
        mock_payload=mock,
    )

    graph = persist_rationale_graph(
        project_id,
        payload.get("ibis"),
        script_version_id=script_version_id,
        allowed_source_types=AUDIENCE_SOURCES,
    )

    result = {
        "naturalness": payload.get("naturalness", ""),
        "ad_sense": payload.get("ad_sense", ""),
        "trust": payload.get("trust", ""),
        "drop_off_risk": payload.get("drop_off_risk", ""),
        "suggestions": payload.get("suggestions") or [],
        "structured_issues": payload.get("structured_issues") or [],
        "proposed_nodes": graph.proposed_nodes,
        "proposed_edges": graph.proposed_edges,
        "node_updates": graph.node_updates,
        "tool_calls_used": ["persist_rationale_graph"],
    }
    log_step(
        "audience_agent",
        phase="OUT",
        project_id=project_id,
        proposed_nodes=len(result["proposed_nodes"]),
        suggestions=result["suggestions"],
    )
    return result
