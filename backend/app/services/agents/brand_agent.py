from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import ValidationError

from app.models.agent_outputs import BrandAgentOutput
from app.repositories.projects import build_brand_insight
from app.services.agent_context import assert_context_isolation, build_agent_context
from app.services.agent_llm import (
    existing_nodes_summary,
    format_quotes,
    invoke_agent_json,
    script_excerpt_for_rows,
)
from app.services.tools.brand_wiki import brand_wiki_lookup
from app.services.tools.ibis_graph import persist_rationale_graph
from app.services.pipeline_log import log_step
from app.services.tavily_client import TavilyClient

BRAND_SOURCES = {"brand_brief", "brand_inferred"}

BrandTaskContext = Literal["brief_parse", "coordinator"]


def _format_requirements_block(brand_perspective: dict[str, Any]) -> str:
    """Render existing requirements as a readable text block for the LLM."""
    lines: list[str] = ["## 已确认品牌需求（来自 Brief 解析）"]

    explicit = brand_perspective.get("explicit_requirements") or []
    lines.append("### 显式需求")
    if explicit:
        for i, req in enumerate(explicit, 1):
            conf = req.get("confidence", "medium")
            lines.append(f"{i}. [{conf}] {req.get('text', '')}")
            if req.get("evidence"):
                lines.append(f"   依据：{req['evidence']}")
    else:
        lines.append("（暂无）")

    implicit = brand_perspective.get("implicit_requirements") or []
    lines.append("### 隐性需求")
    if implicit:
        for i, req in enumerate(implicit, 1):
            conf = req.get("confidence", "medium")
            lines.append(f"{i}. [{conf}] {req.get('text', '')}")
            if req.get("evidence"):
                lines.append(f"   依据：{req['evidence']}")
    else:
        lines.append("（暂无）")

    constraints = brand_perspective.get("constraints") or []
    if constraints:
        lines.append("### 创作约束")
        for c in constraints:
            lines.append(f"- {c}")

    return "\n".join(lines)


async def run_brand_agent(
    project: dict[str, Any],
    *,
    task_context: BrandTaskContext = "coordinator",
    user_message: str | None = None,
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
) -> dict[str, Any]:
    context = build_agent_context("brand", project)
    assert_context_isolation("brand", context)

    brief = context.get("brief") or {}
    text = str(brief.get("text") or brief.get("summary") or "").strip()
    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")

    wiki = await brand_wiki_lookup(brief.get("filename"), brief_text=text)
    tavily_snippets: list[str] = []
    if text:
        tavily = TavilyClient()
        search = await tavily.search(query=text[:120], max_results=2, mock=True)
        tavily_snippets = [
            f"{r.get('title', '报道')}: {r.get('url', '')}" for r in search.get("results", [])[:2]
        ]

    row_ids = set(changed_row_ids or [])
    if quotes:
        for q in quotes:
            if q.get("row_id"):
                row_ids.add(str(q["row_id"]))

    log_step(
        "brand_agent",
        phase="IN",
        project_id=project_id,
        task_context=task_context,
        user_message=user_message,
        quotes=quotes,
        changed_row_ids=sorted(row_ids),
    )

    # Choose brief representation based on calling context.
    # brief_parse (initial or re-parse): inject raw text so the LLM can (re-)extract.
    # coordinator: brief already structured; use existing requirements to avoid redundant
    # re-extraction and give the LLM a stable, token-efficient representation.
    existing_reqs = context.get("brand_perspective_result") or {}
    has_requirements = bool(
        existing_reqs.get("explicit_requirements") or existing_reqs.get("implicit_requirements")
    )

    if task_context == "brief_parse" or not has_requirements:
        brief_section = f"## Brief（原文）\n{text[:3000]}"
    else:
        brief_section = _format_requirements_block(existing_reqs)

    context_block = "\n\n".join(
        [
            brief_section,
            f"## Brand Wiki（{wiki.get('source') or '无匹配手册'}）\n{wiki.get('full_text') or '（未找到对应品牌手册）'}",
            f"## Tavily\n{tavily_snippets}",
            f"## 脚本摘要\n{context.get('script_excerpt', '')}",
            f"## 变动/选段脚本\n{script_excerpt_for_rows(project, row_ids) if row_ids else ''}",
            f"## 用户问题\n{user_message or ''}",
            f"## Quotes\n{format_quotes(quotes)}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        return {
            "explicit_requirements": [{"text": text[:120] or "Brief 约束", "confidence": "high"}],
            "implicit_requirements": [],
            "constraints": [],
            "pr_risks": ["口播感过强"],
            "brand_insights": [
                {
                    "category": "explicit_requirement",
                    "title": "Brief 核心约束",
                    "content": text[:200] or "待对齐品牌要求",
                    "reason": "Brief 解析",
                    "confidence": "high",
                }
            ],
            "ibis": {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "品牌露出优先",
                        "content": text[:300] or "产品核心信息需清晰、前置地呈现。",
                        "source_type": "brand_brief",
                        "source_perspective": "brand",
                    }
                ],
                "edges": [],
            },
        }

    raw_payload = await invoke_agent_json(
        agent_prompt_file="brand_agent.md",
        context=context_block,
        task_type="brand_analyze_brief",
        mock_payload=mock,
    )

    try:
        validated = BrandAgentOutput.model_validate(raw_payload)
        payload = validated.model_dump()
    except ValidationError as exc:
        log_step("brand_agent.schema_validation_failed", phase="WARN", errors=exc.errors())
        payload = raw_payload

    graph = persist_rationale_graph(
        project_id,
        payload.get("ibis"),
        script_version_id=script_version_id,
        allowed_source_types=BRAND_SOURCES,
    )

    brand_insights = []
    for raw in payload.get("brand_insights") or []:
        if not isinstance(raw, dict):
            continue
        brand_insights.append(
            build_brand_insight(
                category=raw.get("category", "explicit_requirement"),
                title=str(raw.get("title", "品牌洞察"))[:120],
                content=str(raw.get("content", "")),
                reason=str(raw.get("reason", "Brand Agent 推理")),
                evidence=raw.get("evidence") if isinstance(raw.get("evidence"), list) else [],
                confidence=raw.get("confidence", "medium"),
                created_by="agent",
            )
        )

    result = {
        "explicit_requirements": payload.get("explicit_requirements") or [],
        "implicit_requirements": payload.get("implicit_requirements") or [],
        "constraints": payload.get("constraints") or [],
        "pr_risks": payload.get("pr_risks") or [],
        "proposed_nodes": graph.proposed_nodes,
        "proposed_edges": graph.proposed_edges,
        "node_updates": graph.node_updates,
        "brand_insights": brand_insights,
        "tool_calls_used": ["tavily_search", "brand_wiki_lookup", "persist_rationale_graph"],
    }
    log_step(
        "brand_agent",
        phase="OUT",
        project_id=project_id,
        proposed_nodes=len(result["proposed_nodes"]),
        brand_insights=len(result["brand_insights"]),
    )
    return result
