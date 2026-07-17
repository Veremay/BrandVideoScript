from __future__ import annotations

from typing import Any, Literal

from pydantic import ValidationError

from app.models.agent_outputs import BrandIbisOutput, BrandRequirementsOutput
from app.repositories.projects import build_brand_insight
from app.services.agent_context import assert_context_isolation, build_agent_context
from app.services.agent_llm import (
    existing_nodes_summary,
    format_quotes,
    format_script_for_prompt,
    invoke_agent_json,
    script_excerpt_for_rows,
)
from app.services.tools.brand_wiki import brand_wiki_context_for_task
from app.services.tools.ibis_graph import persist_rationale_graph
from app.services.pipeline_log import log_step
from app.services.prompt_loader import load_prompt
from app.services.tavily_client import TavilyClient

BRAND_SOURCES = {"brand_brief", "brand_inferred"}

BrandTaskContext = Literal["brief_parse", "coordinator", "issue_response"]


def _format_requirements_block(
    brand_insights: list[dict[str, Any]],
    *,
    constraints: list[str] | None = None,
) -> str:
    """Render brand insights as a readable text block for the LLM."""
    lines: list[str] = ["## 已确认品牌需求（来自 Brief 解析）"]

    explicit = [i for i in brand_insights if i.get("category") == "explicit_requirement"]
    lines.append("### 显式需求")
    if explicit:
        for i, insight in enumerate(explicit, 1):
            conf = insight.get("confidence", "medium")
            title = str(insight.get("title", "")).strip()
            content = str(insight.get("content", "")).strip()
            label = f"{title}: {content}" if title else content
            lines.append(f"{i}. [{conf}] {label}")
            reason = str(insight.get("reason", "")).strip()
            if reason:
                lines.append(f"   Reason：{reason}")
    else:
        lines.append("（暂无）")

    implicit = [i for i in brand_insights if i.get("category") == "implicit_requirement"]
    lines.append("### 隐性需求")
    if implicit:
        for i, insight in enumerate(implicit, 1):
            conf = insight.get("confidence", "medium")
            title = str(insight.get("title", "")).strip()
            content = str(insight.get("content", "")).strip()
            label = f"{title}: {content}" if title else content
            lines.append(f"{i}. [{conf}] {label}")
            reason = str(insight.get("reason", "")).strip()
            if reason:
                lines.append(f"   Reason：{reason}")
    else:
        lines.append("（暂无）")

    if constraints:
        lines.append("### 创作约束")
        for c in constraints:
            lines.append(f"- {c}")

    return "\n".join(lines)


async def run_brand_agent(
    project: dict[str, Any],
    *,
    task_context: BrandTaskContext = "coordinator",
    issue: dict[str, Any] | None = None,
    user_message: str | None = None,
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
    full_script: bool = False,
) -> dict[str, Any]:
    """Dispatch to the appropriate phase based on task_context.

    brief_parse     → _run_requirements_extraction  (reads brief + wiki + tavily)
    coordinator     → _run_nodes_generation         (reads existing requirements)
    issue_response  → _run_issue_response           (one brand position for an issue)
    """
    if task_context == "brief_parse":
        return await _run_requirements_extraction(project)
    if task_context == "issue_response":
        if issue is None:
            raise ValueError("issue is required for issue_response")
        return await _run_issue_response(project, issue=issue)
    return await _run_nodes_generation(
        project,
        user_message=user_message,
        quotes=quotes,
        changed_row_ids=changed_row_ids,
        full_script=full_script,
    )


async def _run_requirements_extraction(project: dict[str, Any]) -> dict[str, Any]:
    """brief_parse 触发：从 Brief + Wiki + Tavily 提取品牌需求，不生成 IBIS 节点。"""
    context = build_agent_context("brand", project)
    assert_context_isolation("brand", context)

    brief = context.get("brief") or {}
    text = str(brief.get("text") or brief.get("summary") or "").strip()
    project_id = str(context.get("project_id") or project.get("_id") or "")

    wiki_context = await brand_wiki_context_for_task(
        brand_identifier=brief.get("filename"),
        brief_text=text,
        task="extract_requirements",
    )
    wiki = {
        "source": wiki_context.get("source"),
        "full_text": wiki_context.get("context"),
    }
    tavily_snippets: list[str] = []
    if text:
        tavily = TavilyClient()
        search = await tavily.search(query=text[:120], max_results=2, mock=True)
        tavily_snippets = [
            f"{r.get('title', '报道')}: {r.get('url', '')}" for r in search.get("results", [])[:2]
        ]

    log_step("brand_agent.extract_requirements", phase="IN", project_id=project_id)

    public_sources = "\n".join(tavily_snippets) if tavily_snippets else "（无）"
    context_block = "\n\n".join([
        f"## Brief（原文）\n{text[:3000]}",
        f"## 品牌知识\n{wiki.get('full_text') or '（未找到对应品牌知识）'}",
        f"## 公开资料\n{public_sources}",
    ])

    def mock() -> dict[str, Any]:
        return {
            "constraints": [],
            "pr_risks": ["口播感过强"],
            "brand_insights": [{
                "category": "explicit_requirement",
                "title": "Brief 核心约束",
                "content": text[:200] or "待对齐品牌要求",
                "reason": "Brief 解析",
                "confidence": "high",
            }],
        }

    raw = await invoke_agent_json(
        agent_prompt_file="brand_agent.md",
        context=context_block,
        task_type="brand_extract_requirements",
        mock_payload=mock,
        extra_vars={
            "TASK_INSTRUCTIONS": load_prompt("tasks/brand_phase1_instructions.md"),
            "OUTPUT_SCHEMA": load_prompt("tasks/brand_phase1_output.md"),
        },
    )

    try:
        validated = BrandRequirementsOutput.model_validate(raw)
        payload = validated.model_dump(exclude_none=True)
    except ValidationError as exc:
        log_step("brand_agent.extract_requirements.validation_failed", phase="WARN", errors=exc.errors())
        payload = raw

    brand_insights = _build_insights(payload)
    explicit_count = sum(1 for i in brand_insights if i.get("category") == "explicit_requirement")
    implicit_count = sum(1 for i in brand_insights if i.get("category") == "implicit_requirement")
    result = {
        "constraints": payload.get("constraints") or [],
        "pr_risks": payload.get("pr_risks") or [],
        "proposed_nodes": [],
        "proposed_edges": [],
        "node_updates": [],
        "brand_insights": brand_insights,
        "tool_calls_used": ["brand_wiki_search", "brand_wiki_read", "tavily_search"],
    }
    log_step(
        "brand_agent.extract_requirements",
        phase="OUT",
        project_id=project_id,
        explicit=explicit_count,
        implicit=implicit_count,
        brand_insights=len(brand_insights),
    )
    return result


async def _run_nodes_generation(
    project: dict[str, Any],
    *,
    user_message: str | None = None,
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
    full_script: bool = False,
) -> dict[str, Any]:
    """coordinator 触发：从已有需求生成 IBIS position 节点，不重读 Brief/Wiki。"""
    context = build_agent_context("brand", project)
    assert_context_isolation("brand", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")

    row_ids = set(changed_row_ids or [])
    if quotes:
        for q in quotes:
            if q.get("row_id"):
                row_ids.add(str(q["row_id"]))

    log_step(
        "brand_agent.generate_nodes",
        phase="IN",
        project_id=project_id,
        user_message=user_message,
        changed_row_ids=sorted(row_ids),
    )

    brand_insights = context.get("brand_insights") or []
    existing_reqs = context.get("brand_perspective_result") or {}
    req_block = _format_requirements_block(
        brand_insights,
        constraints=existing_reqs.get("constraints") or [],
    )
    if full_script:
        script_block = f"## 当前脚本\n{format_script_for_prompt(project)}"
    elif row_ids:
        script_block = f"## 变动脚本\n{script_excerpt_for_rows(project, row_ids)}"
    else:
        script_block = "## 变动脚本\n（无变动）"
    context_block = "\n\n".join([
        req_block,
        script_block,
        f"## 用户问题\n{user_message or '（无）'}",
        f"## Quotes\n{format_quotes(quotes)}",
        f"## 已有节点\n{existing_nodes_summary(project)}",
    ])

    brief_text = str((context.get("brief") or {}).get("text") or "").strip()

    def mock() -> dict[str, Any]:
        return {
            "ibis": {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "品牌露出优先",
                        "content": "品牌核心信息需要更清晰、前置地呈现，但露出方式仍需避免破坏内容自然度。",
                        "source_type": "brand_brief",
                        "source_perspective": "brand",
                    },
                    {
                        "node_type": "argument",
                        "title": "Brief 明确要求核心信息可见",
                        "content": (brief_text[:180] if brief_text else "Brief 要求产品核心信息被观众清楚接收。"),
                        "source_type": "brand_brief",
                        "source_perspective": "brand",
                    },
                ],
                "edges": [{"from_index": 1, "to_index": 0, "relation_type": "supports"}],
                "external_edges": [],
                "node_updates": [],
            }
        }

    raw = await invoke_agent_json(
        agent_prompt_file="brand_agent.md",
        context=context_block,
        task_type="brand_generate_nodes",
        mock_payload=mock,
        extra_vars={
            "TASK_INSTRUCTIONS": load_prompt("tasks/brand_phase2_instructions.md"),
            "OUTPUT_SCHEMA": load_prompt("tasks/brand_phase2_output.md"),
        },
    )

    try:
        validated = BrandIbisOutput.model_validate(raw)
        payload = validated.model_dump(exclude_none=True)
    except ValidationError as exc:
        log_step("brand_agent.generate_nodes.validation_failed", phase="WARN", errors=exc.errors())
        payload = raw

    graph = persist_rationale_graph(
        project_id,
        payload.get("ibis"),
        script_version_id=script_version_id,
        allowed_source_types=BRAND_SOURCES,
        allow_unlinked_positions=True,
    )
    result = {
        "constraints": [],
        "pr_risks": [],
        "proposed_nodes": graph.proposed_nodes,
        "proposed_edges": graph.proposed_edges,
        "node_updates": graph.node_updates,
        "brand_insights": [],
        "tool_calls_used": ["persist_rationale_graph"],
    }
    log_step(
        "brand_agent.generate_nodes",
        phase="OUT",
        project_id=project_id,
        proposed_nodes=len(result["proposed_nodes"]),
    )
    return result


async def _run_issue_response(
    project: dict[str, Any],
    *,
    issue: dict[str, Any],
) -> dict[str, Any]:
    """Generate brand position + arguments responding to a user-created issue."""
    context = build_agent_context("brand", project)
    assert_context_isolation("brand", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    issue_id = str(issue.get("node_id") or "")
    issue_title = str(issue.get("title") or "")
    issue_content = str(issue.get("content") or "")

    brand_insights = context.get("brand_insights") or []
    existing_reqs = context.get("brand_perspective_result") or {}
    req_block = _format_requirements_block(
        brand_insights,
        constraints=existing_reqs.get("constraints") or [],
    )

    log_step(
        "brand_agent.issue_response",
        phase="IN",
        project_id=project_id,
        issue_id=issue_id,
        issue_title=issue_title,
    )

    context_block = "\n\n".join([
        f"## 目标 Issue\nid={issue_id}\n标题：{issue_title}\n内容：{issue_content}",
        req_block,
        f"## 已有节点\n{existing_nodes_summary(project)}",
    ])

    def mock() -> dict[str, Any]:
        label = issue_title[:30] or "该议题"
        return {
            "ibis": {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "品牌立场",
                        "content": f"针对「{label}」，品牌方更关注 Brief 约束与核心信息露出。",
                        "source_type": "brand_brief",
                        "source_perspective": "brand",
                    },
                    {
                        "node_type": "argument",
                        "title": "Brief 依据",
                        "content": f"品牌需求明确要求在「{label}」相关段落体现核心信息。",
                        "source_type": "brand_brief",
                        "source_perspective": "brand",
                    },
                ],
                "edges": [
                    {"from_index": 1, "to_index": 0, "relation_type": "supports"},
                ],
                "external_edges": [
                    {"from_index": 0, "to_node_id": issue_id, "relation_type": "responds_to"},
                ],
                "node_updates": [],
            }
        }

    raw = await invoke_agent_json(
        agent_prompt_file="brand_agent.md",
        context=context_block,
        task_type="brand_issue_response",
        mock_payload=mock,
        extra_vars={
            "TASK_INSTRUCTIONS": load_prompt("tasks/brand_issue_response_instructions.md"),
            "OUTPUT_SCHEMA": load_prompt("tasks/brand_issue_response_output.md").replace(
                "<issue_id>", issue_id
            ),
        },
    )

    try:
        validated = BrandIbisOutput.model_validate(raw)
        payload = validated.model_dump(exclude_none=True)
    except ValidationError as exc:
        log_step("brand_agent.issue_response.validation_failed", phase="WARN", errors=exc.errors())
        payload = raw

    graph = persist_rationale_graph(
        project_id,
        payload.get("ibis"),
        script_version_id=script_version_id,
        allowed_source_types=BRAND_SOURCES,
    )
    result = {
        "constraints": [],
        "pr_risks": [],
        "proposed_nodes": graph.proposed_nodes,
        "proposed_edges": graph.proposed_edges,
        "node_updates": graph.node_updates,
        "brand_insights": [],
        "tool_calls_used": ["persist_rationale_graph"],
    }
    log_step(
        "brand_agent.issue_response",
        phase="OUT",
        project_id=project_id,
        proposed_nodes=len(result["proposed_nodes"]),
    )
    return result


def _build_insights(payload: dict[str, Any]) -> list[dict[str, Any]]:
    insights = []
    for raw in payload.get("brand_insights") or []:
        if not isinstance(raw, dict):
            continue
        insights.append(
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
    return insights
