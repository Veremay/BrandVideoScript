from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import ValidationError

from app.models.agent_outputs import BrandAgentOutput, BrandIbisOutput, BrandRequirementsOutput
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

BrandTaskContext = Literal["brief_parse", "coordinator", "issue_response"]

# ---------------------------------------------------------------------------
# Phase-specific prompt fragments injected into brand_agent.md placeholders
# ---------------------------------------------------------------------------

_PHASE1_TASK_INSTRUCTIONS = """\
## 任务：品牌需求提取

分析 Brief 与辅助检索结果，提取结构化品牌需求与洞察。
专注于需求识别，**不需要生成 IBIS 节点**。"""

_PHASE1_OUTPUT_SCHEMA = """\
## 输出 JSON（仅需求字段，不要 ibis）

字段枚举约束（严格使用以下值，不得自造）：
- `brand_insights[].category`：`"explicit_requirement"` | `"implicit_requirement"`
  - Brief 解析阶段禁止使用 `brand_feedback`；风险预判归入 `"implicit_requirement"`
- `brand_insights[].confidence`：`"high"` | `"medium"` | `"low"`

```json
{
  "explicit_requirements": [{ "text": "…", "confidence": "high|medium|low" }],
  "implicit_requirements": [{ "text": "…", "confidence": "high|medium|low" }],
  "constraints": ["纯文本，约束条件放这里"],
  "pr_risks": ["纯文本，审片风险放这里"],
  "brand_insights": [
    { "category": "explicit_requirement", "title": "…", "content": "…", "reason": "…", "confidence": "high" }
  ]
}
```"""

_PHASE2_TASK_INSTRUCTIONS = """\
## 任务：品牌立场节点生成

基于已提取的品牌需求，推理品牌方立场，生成 IBIS position 节点。
- Brand 侧**只产 position**，不要产 issue（冲突由 Expert 汇总后判定）
- `source_type` 限：`brand_brief`、`brand_inferred`
- position 可独立存在，**不要写 edges**"""

_PHASE2_OUTPUT_SCHEMA = """\
## 输出 JSON（仅 ibis 节点，不要需求字段）

字段枚举约束：
- `nodes[].node_type`：`"position"`（Brand 侧只产 position）
- `nodes[].source_type`：`"brand_brief"` | `"brand_inferred"`

```json
{
  "ibis": {
    "nodes": [
      { "node_type": "position", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" }
    ],
    "edges": [],
    "external_edges": [],
    "node_updates": []
  }
}
```

{{IBIS_TYPES}}"""

_ISSUE_RESPONSE_TASK_INSTRUCTIONS = """\
## 任务：针对用户 Issue 生成品牌立场

用户提出了一个议题（Issue）。从品牌方视角给出**唯一一条** position 立场。
- 仅输出 1 个 position 节点
- 用 external_edges 将该 position（from_index: 0）以 responds_to 连到目标 issue（to_node_id）
- position 的 source_type 限：`brand_brief`、`brand_inferred`
- 不要输出 issue 节点"""

_ISSUE_RESPONSE_OUTPUT_SCHEMA = """\
## 输出 JSON（仅 ibis 节点）

```json
{
  "ibis": {
    "nodes": [
      { "node_type": "position", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" }
    ],
    "edges": [],
    "external_edges": [
      { "from_index": 0, "to_node_id": "<issue_id>", "relation_type": "responds_to" }
    ],
    "node_updates": []
  }
}
```"""


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
    issue: dict[str, Any] | None = None,
    user_message: str | None = None,
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
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
    )


async def _run_requirements_extraction(project: dict[str, Any]) -> dict[str, Any]:
    """brief_parse 触发：从 Brief + Wiki + Tavily 提取品牌需求，不生成 IBIS 节点。"""
    context = build_agent_context("brand", project)
    assert_context_isolation("brand", context)

    brief = context.get("brief") or {}
    text = str(brief.get("text") or brief.get("summary") or "").strip()
    project_id = str(context.get("project_id") or project.get("_id") or "")

    wiki = await brand_wiki_lookup(brief.get("filename"), brief_text=text)
    tavily_snippets: list[str] = []
    if text:
        tavily = TavilyClient()
        search = await tavily.search(query=text[:120], max_results=2, mock=True)
        tavily_snippets = [
            f"{r.get('title', '报道')}: {r.get('url', '')}" for r in search.get("results", [])[:2]
        ]

    log_step("brand_agent.extract_requirements", phase="IN", project_id=project_id)

    context_block = "\n\n".join([
        f"## Brief（原文）\n{text[:3000]}",
        f"## Brand Wiki（{wiki.get('source') or '无匹配手册'}）\n{wiki.get('full_text') or '（未找到对应品牌手册）'}",
        f"## Tavily\n{tavily_snippets}",
    ])

    def mock() -> dict[str, Any]:
        return {
            "explicit_requirements": [{"text": text[:120] or "Brief 约束", "confidence": "high"}],
            "implicit_requirements": [],
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
            "TASK_INSTRUCTIONS": _PHASE1_TASK_INSTRUCTIONS,
            "OUTPUT_SCHEMA": _PHASE1_OUTPUT_SCHEMA,
        },
    )

    try:
        validated = BrandRequirementsOutput.model_validate(raw)
        payload = validated.model_dump(exclude_none=True)
    except ValidationError as exc:
        log_step("brand_agent.extract_requirements.validation_failed", phase="WARN", errors=exc.errors())
        payload = raw

    brand_insights = _build_insights(payload)
    result = {
        "explicit_requirements": payload.get("explicit_requirements") or [],
        "implicit_requirements": payload.get("implicit_requirements") or [],
        "constraints": payload.get("constraints") or [],
        "pr_risks": payload.get("pr_risks") or [],
        "proposed_nodes": [],
        "proposed_edges": [],
        "node_updates": [],
        "brand_insights": brand_insights,
        "tool_calls_used": ["brand_wiki_lookup", "tavily_search"],
    }
    log_step(
        "brand_agent.extract_requirements",
        phase="OUT",
        project_id=project_id,
        explicit=len(result["explicit_requirements"]),
        implicit=len(result["implicit_requirements"]),
        brand_insights=len(brand_insights),
    )
    return result


async def _run_nodes_generation(
    project: dict[str, Any],
    *,
    user_message: str | None = None,
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
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

    existing_reqs = context.get("brand_perspective_result") or {}
    req_summary = json.dumps(
        {
            "explicit_requirements": existing_reqs.get("explicit_requirements") or [],
            "implicit_requirements": existing_reqs.get("implicit_requirements") or [],
            "constraints": existing_reqs.get("constraints") or [],
        },
        ensure_ascii=False,
        indent=2,
    )
    context_block = "\n\n".join([
        f"## 品牌需求（已提取）\n{req_summary}",
        f"## 变动脚本\n{script_excerpt_for_rows(project, row_ids) if row_ids else '（无变动）'}",
        f"## 用户问题\n{user_message or '（无）'}",
        f"## Quotes\n{format_quotes(quotes)}",
        f"## 已有节点\n{existing_nodes_summary(project)}",
    ])

    brief_text = str((context.get("brief") or {}).get("text") or "").strip()

    def mock() -> dict[str, Any]:
        return {
            "ibis": {
                "nodes": [{
                    "node_type": "position",
                    "title": "品牌露出优先",
                    "content": brief_text[:300] or "产品核心信息需清晰、前置地呈现。",
                    "source_type": "brand_brief",
                    "source_perspective": "brand",
                }],
                "edges": [],
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
            "TASK_INSTRUCTIONS": _PHASE2_TASK_INSTRUCTIONS,
            "OUTPUT_SCHEMA": _PHASE2_OUTPUT_SCHEMA,
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
    )
    result = {
        "explicit_requirements": [],
        "implicit_requirements": [],
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
    """Generate a single brand position responding to a user-created issue."""
    context = build_agent_context("brand", project)
    assert_context_isolation("brand", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    issue_id = str(issue.get("node_id") or "")
    issue_title = str(issue.get("title") or "")
    issue_content = str(issue.get("content") or "")

    existing_reqs = context.get("brand_perspective_result") or {}
    req_summary = json.dumps(
        {
            "explicit_requirements": existing_reqs.get("explicit_requirements") or [],
            "implicit_requirements": existing_reqs.get("implicit_requirements") or [],
            "constraints": existing_reqs.get("constraints") or [],
        },
        ensure_ascii=False,
        indent=2,
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
        f"## 品牌需求（已提取）\n{req_summary}",
        f"## 已有节点\n{existing_nodes_summary(project)}",
    ])

    def mock() -> dict[str, Any]:
        label = issue_title[:30] or "该议题"
        return {
            "ibis": {
                "nodes": [{
                    "node_type": "position",
                    "title": "品牌立场",
                    "content": f"针对「{label}」，品牌方更关注 Brief 约束与核心信息露出。",
                    "source_type": "brand_brief",
                    "source_perspective": "brand",
                }],
                "edges": [],
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
            "TASK_INSTRUCTIONS": _ISSUE_RESPONSE_TASK_INSTRUCTIONS,
            "OUTPUT_SCHEMA": _ISSUE_RESPONSE_OUTPUT_SCHEMA.replace("<issue_id>", issue_id),
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
        "explicit_requirements": [],
        "implicit_requirements": [],
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
