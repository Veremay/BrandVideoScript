from __future__ import annotations

from typing import Any, Literal

from app.services.agent_context import assert_context_isolation, build_agent_context
from app.services.agent_llm import (
    existing_nodes_summary,
    format_quotes,
    format_script_for_prompt,
    invoke_agent_json,
    script_excerpt_for_rows,
)
from app.services.pipeline_log import log_step
from app.services.tools.ibis_graph import persist_rationale_graph

AUDIENCE_SOURCES = {"audience_persona", "audience_simulation"}

AudienceTaskContext = Literal["coordinator", "issue_response"]

_DEFAULT_TASK_INSTRUCTIONS = """\
## 你的任务

1. 评估自然度、广告感、信任门槛、划走风险。
2. 推理观众向 **IBIS position（观众立场 / 期待）**，通过 `ibis` 字段交给 **`persist_rationale_graph`** 落库。
3. 产出 position + real argument（把观众视角表达为明确立场，并给出真实理由）；**不要产 issue**。`source_type` 限：`audience_persona`、`audience_simulation`。系统会为未连接的 position 补充承载 Issue；map_update 中必须写 argument → position 的 `supports`/`opposes` edges；冲突由 **Coordinator** 后续分析并分配 `conflict_tags`。"""

_DEFAULT_TASK_INSTRUCTIONS += """

## Map update tension requirements
- Do not default to supporting the current script.
- Generate positions from audience friction or drop-off risk, not only positive reactions.
- Prefer concrete tensions that surface trade-offs against brand requirements or creator strategy.
- A useful audience position says what feels forced, unclear, too slow, too dense, or likely to reduce trust.
- Every generated position must include a real argument connected with `supports` or `opposes`; do not rely on placeholder arguments.
"""

_DEFAULT_OUTPUT_SCHEMA = """\
## 输出 JSON

```json
{
  "naturalness": "…",
  "ad_sense": "…",
  "trust": "…",
  "drop_off_risk": "…",
  "suggestions": ["…"],
  "structured_issues": [{ "title": "…", "content": "…" }],
  "ibis": {
    "nodes": [],
    "edges": [],
    "external_edges": [],
    "node_updates": []
  }
}
```"""

_ISSUE_RESPONSE_TASK_INSTRUCTIONS = """\
## 任务：针对用户 Issue 生成观众立场与论据

用户提出了一个议题（Issue）。从当前 Persona 视角给出：
- **1 个 position** 节点（观众立场）
- **1~2 个 argument** 节点（支撑或反对该 position 的理由）
- 用 `external_edges` 将 position（from_index: 0）以 `responds_to` 连到目标 issue（to_node_id）
- 用 `edges` 将每个 argument（from_index）以 `supports` 或 `opposes` 连到 position（to_index: 0）
- position / argument 的 `source_type` 限：`audience_persona`、`audience_simulation`
- 不要输出 issue 节点"""

_ISSUE_RESPONSE_OUTPUT_SCHEMA = """\
## 输出 JSON

```json
{
  "ibis": {
    "nodes": [
      { "node_type": "position", "title": "…", "content": "…", "source_type": "audience_simulation", "source_perspective": "audience" },
      { "node_type": "argument", "title": "…", "content": "…", "source_type": "audience_simulation", "source_perspective": "audience" }
    ],
    "edges": [
      { "from_index": 1, "to_index": 0, "relation_type": "supports" }
    ],
    "external_edges": [
      { "from_index": 0, "to_node_id": "<issue_id>", "relation_type": "responds_to" }
    ]
  }
}
```"""


async def run_audience_agent(
    project: dict[str, Any],
    *,
    task_context: AudienceTaskContext = "coordinator",
    issue: dict[str, Any] | None = None,
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
    full_script: bool = False,
) -> dict[str, Any]:
    context = build_agent_context("audience", project)
    assert_context_isolation("audience", context)

    persona = context.get("active_persona")
    if not persona:
        raise ValueError("Active persona is required for audience analysis")

    if task_context == "issue_response":
        if issue is None:
            raise ValueError("issue is required for issue_response")
        return await _run_issue_response(project, issue=issue, persona=persona)

    return await _run_script_analysis(
        project,
        context=context,
        persona=persona,
        quotes=quotes,
        changed_row_ids=changed_row_ids,
        full_script=full_script,
    )


async def _run_script_analysis(
    project: dict[str, Any],
    *,
    context: dict[str, Any],
    persona: dict[str, Any],
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
    full_script: bool = False,
) -> dict[str, Any]:
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

    if full_script:
        script_block = f"## 当前脚本\n{format_script_for_prompt(project)}"
    elif row_ids:
        script_block = f"## 变动/选段脚本\n{script_excerpt_for_rows(project, row_ids)}"
    else:
        script_block = f"## 脚本摘要\n{context.get('script_excerpt', '')}"

    context_block = "\n\n".join(
        [
            f"## Persona\n{persona}",
            f"## 平台\n{context.get('platform_context', 'other')}",
            script_block,
            f"## Quotes\n{format_quotes(quotes)}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        return {
            "naturalness": f"以 {persona.get('name')} 视角评估",
            "ad_sense": "需降低硬广感",
            "trust": persona.get("reason") or persona.get("explanation") or "真实体验",
            "drop_off_risk": persona.get("explanation") or "硬广话术",
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
                    },
                    {
                        "node_type": "argument",
                        "title": "硬广表达会提高流失风险",
                        "content": "Persona 对广告感和不自然植入敏感，过早或过重的产品表达可能降低信任和完播。",
                        "source_type": "audience_simulation",
                        "source_perspective": "audience",
                    }
                ],
                "edges": [{"from_index": 1, "to_index": 0, "relation_type": "supports"}],
            },
        }

    payload = await invoke_agent_json(
        agent_prompt_file="audience_agent.md",
        context=context_block,
        task_type="audience_analyze_script",
        mock_payload=mock,
        extra_vars={
            "TASK_INSTRUCTIONS": _DEFAULT_TASK_INSTRUCTIONS,
            "OUTPUT_SCHEMA": _DEFAULT_OUTPUT_SCHEMA,
        },
    )

    graph = persist_rationale_graph(
        project_id,
        payload.get("ibis"),
        script_version_id=script_version_id,
        allowed_source_types=AUDIENCE_SOURCES,
        allow_unlinked_positions=True,
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


async def _run_issue_response(
    project: dict[str, Any],
    *,
    issue: dict[str, Any],
    persona: dict[str, Any],
) -> dict[str, Any]:
    context = build_agent_context("audience", project)
    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    issue_id = str(issue.get("node_id") or "")
    issue_title = str(issue.get("title") or "")
    issue_content = str(issue.get("content") or "")

    log_step(
        "audience_agent.issue_response",
        phase="IN",
        project_id=project_id,
        issue_id=issue_id,
        persona_id=persona.get("persona_id"),
    )

    context_block = "\n\n".join(
        [
            f"## 目标 Issue\nid={issue_id}\n标题：{issue_title}\n内容：{issue_content}",
            f"## Persona\n{persona}",
            f"## 平台\n{context.get('platform_context', 'other')}",
            f"## 脚本摘要\n{context.get('script_excerpt', '')}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        label = issue_title[:30] or "该议题"
        return {
            "naturalness": f"以 {persona.get('name')} 视角回应议题",
            "ad_sense": "",
            "trust": "",
            "drop_off_risk": "",
            "suggestions": [],
            "structured_issues": [],
            "ibis": {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "观众立场",
                        "content": f"针对「{label}」，{persona.get('name', '观众')}更关注内容自然性与信任感。",
                        "source_type": "audience_simulation",
                        "source_perspective": "audience",
                    },
                    {
                        "node_type": "argument",
                        "title": "Persona 反应",
                        "content": f"{persona.get('name', '观众')}对硬广话术敏感，自然表达更易建立信任。",
                        "source_type": "audience_simulation",
                        "source_perspective": "audience",
                    },
                ],
                "edges": [
                    {"from_index": 1, "to_index": 0, "relation_type": "supports"},
                ],
                "external_edges": [
                    {"from_index": 0, "to_node_id": issue_id, "relation_type": "responds_to"},
                ],
            },
        }

    payload = await invoke_agent_json(
        agent_prompt_file="audience_agent.md",
        context=context_block,
        task_type="audience_issue_response",
        mock_payload=mock,
        extra_vars={
            "TASK_INSTRUCTIONS": _ISSUE_RESPONSE_TASK_INSTRUCTIONS,
            "OUTPUT_SCHEMA": _ISSUE_RESPONSE_OUTPUT_SCHEMA.replace("<issue_id>", issue_id),
        },
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
        "audience_agent.issue_response",
        phase="OUT",
        project_id=project_id,
        proposed_nodes=len(result["proposed_nodes"]),
    )
    return result
