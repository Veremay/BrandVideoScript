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
from app.services.tavily_client import TavilyClient

BRAND_SOURCES = {"brand_brief", "brand_inferred"}

BrandTaskContext = Literal["brief_parse", "coordinator", "issue_response"]

# ---------------------------------------------------------------------------
# Phase-specific prompt fragments injected into brand_agent.md placeholders
# ---------------------------------------------------------------------------

_PHASE1_TASK_INSTRUCTIONS = """\
## 任务：品牌需求提取

分析 Brief 与辅助检索结果，提取结构化品牌需求与洞察。
专注于需求识别，**不需要生成 IBIS 节点**。

## 5W1H 分析框架

提取需求前，先在内部使用 5W1H 对材料进行交叉分析。5W1H 是分析工具，不是必须逐项输出的问卷：
- **Who**：品牌希望影响谁？区分目标受众、购买者、使用者与传播对象。
- **What**：品牌要求传达什么？识别核心卖点、产品信息、品牌价值、必选项与禁区。
- **Why**：品牌为什么提出该要求？判断它服务的传播目标、商业目标或要规避的品牌风险。
- **When**：信息应在视频哪个阶段出现？是否涉及发布时间、活动节点、使用时机或露出顺序？
- **Where**：产品与品牌信息应在什么场景、渠道、画面位置或内容语境中呈现？
- **How**：应以什么叙事方式、语气、视觉风格、口播方式和露出强度呈现？

分析要求：
1. 不要为了填满 5W1H 补造信息；缺少依据的维度保持未知，不得输出为确定需求。
2. 合并多个维度共同指向的结论，避免把同一要求拆成多条重复洞察。
3. 明确区分来源：材料直接说明的归为 `explicit_requirement`；有材料依据但需要推断的归为 `implicit_requirement`。
4. 每条洞察应说明品牌具体希望什么、为什么重要，以及对视频创作有什么可执行影响。
5. 主动识别维度之间的张力，例如信息完整度与露出时长、受众接受习惯与品牌表达方式、自然场景与强露出要求之间的冲突。
6. 最终只输出综合后的可执行需求，不要输出 5W1H 问答过程或六项清单。"""

_PHASE1_OUTPUT_SCHEMA = """\
## 输出 JSON（仅需求字段，不要 ibis）

字段枚举约束（严格使用以下值，不得自造）：
- `brand_insights[].category`：`"explicit_requirement"` | `"implicit_requirement"`
  - Brief 解析阶段禁止使用 `brand_feedback`；风险预判归入 `"implicit_requirement"`
- `brand_insights[].confidence`：`"high"` | `"medium"` | `"low"`

```json
{
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
- Brand 侧产 position + real argument，不要产 issue；系统会为未连接的 position 补充承载 Issue，冲突由 **Coordinator** 后续分析并分配 `conflict_tags`
- `source_type` 限：`brand_brief`、`brand_inferred`
- map_update 中必须写 argument → position 的 `supports`/`opposes` edges；如果任务明确给定目标 Issue，才用 `responds_to` 连接"""

_PHASE2_TASK_INSTRUCTIONS += """

## 5W1H 立场完整性检查
- **Who**：该立场保护哪类目标对象或品牌关系？
- **What**：品牌具体要求改变、加强、前置、明确或保留什么？
- **Why**：支持该立场的依据和不执行的风险是什么？
- **When / Where**：是否需要明确脚本阶段、行、场景或露出位置？
- **How**：是否给出了可执行的呈现方向？
- 不要求每个立场机械覆盖全部六项；只保留与当前脚本改动或 Issue 有关且有依据的维度。
- 5W1H 仅用于内部检查，不要输出问答清单。

## Map update tension requirements
- Do not default to supporting the current script.
- Generate positions from brand requirements, risks, and non-negotiables.
- Prefer concrete tensions that Coordinator can compare with audience or creator positions.
- A useful brand position says what must be strengthened, protected, moved earlier, made clearer, or treated as unacceptable.
- Every generated position must include a real argument connected with `supports` or `opposes`; do not rely on placeholder arguments.
- Position content should be a concise stance, not pasted Brief text. Put evidence or Brief wording in the argument.
"""

_PHASE2_OUTPUT_SCHEMA = """\
## 输出 JSON（仅 ibis 节点，不要需求字段）

字段枚举约束：
- `nodes[].node_type`：`"position"` 或 `"argument"`（Brand 侧不产 issue）
- `nodes[].source_type`：`"brand_brief"` | `"brand_inferred"`

```json
{
  "ibis": {
    "nodes": [
      { "node_type": "position", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" },
      { "node_type": "argument", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" }
    ],
    "edges": [
      { "from_index": 1, "to_index": 0, "relation_type": "supports" }
    ],
    "external_edges": [],
    "node_updates": []
  }
}
```

{{IBIS_TYPES}}"""

_ISSUE_RESPONSE_TASK_INSTRUCTIONS = """\
## 任务：针对用户 Issue 生成品牌立场与论据

用户提出了一个议题（Issue）。从品牌方视角给出：
- **1 个 position** 节点（品牌立场）
- **1~2 个 argument** 节点（支撑或反对该 position 的理由）
- 用 `external_edges` 将 position（from_index: 0）以 `responds_to` 连到目标 issue（to_node_id）
- 用 `edges` 将每个 argument（from_index）以 `supports` 或 `opposes` 连到 position（to_index: 0）
- position / argument 的 `source_type` 限：`brand_brief`、`brand_inferred`
- 不要输出 issue 节点"""

_ISSUE_RESPONSE_OUTPUT_SCHEMA = """\
## 输出 JSON（仅 ibis 节点）

```json
{
  "ibis": {
    "nodes": [
      { "node_type": "position", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" },
      { "node_type": "argument", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" }
    ],
    "edges": [
      { "from_index": 1, "to_index": 0, "relation_type": "supports" }
    ],
    "external_edges": [
      { "from_index": 0, "to_node_id": "<issue_id>", "relation_type": "responds_to" }
    ],
    "node_updates": []
  }
}
```"""


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

    context_block = "\n\n".join([
        f"## Brief（原文）\n{text[:3000]}",
        f"## Brand Wiki（{wiki.get('source') or '无匹配手册'}）\n{wiki.get('full_text') or '（未找到对应品牌手册）'}",
        f"## Tavily\n{tavily_snippets}",
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
