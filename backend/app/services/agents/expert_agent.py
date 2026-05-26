from __future__ import annotations

import json
from typing import Any

from app.services.agent_context import assert_context_isolation, build_agent_context
from app.services.agent_llm import (
    existing_nodes_summary,
    format_quotes,
    invoke_agent_json,
    perspective_result_json,
    script_excerpt_for_rows,
)
from app.services.pipeline_log import log_step
from app.services.tools.expert_kb import domain_case_retriever, script_structure_kb
from app.models.modification_scheme_ops import (
    find_editable_text_column,
    get_cell_value,
    normalize_scheme,
)
from app.services.tools.ibis_graph import persist_rationale_graph

EXPERT_SOURCES = {"expert_strategy"}

DIRECTION_LABELS = {
    "conservative": "保守（品牌优先）",
    "balanced": "平衡",
    "creator_led": "创作者主导",
    "audience_friendly": "观众友好",
}


def _pick_target_issues(project: dict[str, Any], target_issue_ids: list[str] | None) -> list[dict[str, Any]]:
    nodes = project.get("rationale_nodes") or []
    issues = [n for n in nodes if n.get("node_type") == "issue"]
    if target_issue_ids:
        wanted = set(target_issue_ids)
        filtered = [n for n in issues if n.get("node_id") in wanted]
        return filtered or issues[:3]
    prioritized = [
        n
        for n in issues
        if n.get("status") in {"open", "needs_negotiation", "in_review"}
        or n.get("in_negotiation_queue")
    ]
    return prioritized[:3] or issues[:2]


def _mock_modification_schemes(
    project: dict[str, Any],
    *,
    target_issues: list[dict[str, Any]],
    user_message: str | None,
) -> list[dict[str, Any]]:
    project_id = str(project.get("_id") or "")
    script = project.get("current_script") or {}
    script_version_id = project.get("current_script_version_id")
    columns_by_key = {c.get("key"): c for c in script.get("columns", [])}
    scene_col = columns_by_key.get("scene") or find_editable_text_column(script)
    notes_col = columns_by_key.get("notes")
    rows = sorted(script.get("rows", []), key=lambda r: r.get("order", 0))[:3]
    issue_ids = [n["node_id"] for n in target_issues if n.get("node_id")]
    issue_title = target_issues[0].get("title", "脚本冲突") if target_issues else "整体脚本"

    directions = ["conservative", "balanced", "creator_led", "audience_friendly"]
    schemes: list[dict[str, Any]] = []

    def _propose_added(direction: str, current: str, *, slot: str) -> str:
        if direction == "conservative":
            return f"{current}（强化品牌露出）".strip() if current else "品牌核心信息前置"
        if direction == "audience_friendly":
            return current.replace("广告", "内容") if current else "以故事化口吻降低推销感"
        if direction == "creator_led":
            return f"{current} — 保留创作者叙事节奏".strip() if current else "创作者视角的叙事开场"
        if slot == "notes":
            return f"{current}｜补充可协商说明".strip() if current else "创作者补充说明（可协商）"
        return f"{current}（平衡品牌与叙事）".strip() if current else "兼顾品牌信息与观众体验"

    for direction in directions[:3]:
        hunks: list[dict[str, Any]] = []
        for row_index, row in enumerate(rows):
            targets: list[tuple[dict, str]] = []
            if scene_col:
                targets.append((scene_col, "scene"))
            if notes_col and row_index == 0:
                targets.append((notes_col, "notes"))
            for column, slot in targets:
                row_id = row["row_id"]
                column_id = column["column_id"]
                current = get_cell_value(script, row_id, column_id) or ""
                added = _propose_added(direction, current, slot=slot)
                if added != current:
                    hunks.append(
                        {
                            "row_id": row_id,
                            "column_id": column_id,
                            "context": f"第{row_index + 1}镜 · {column.get('label', slot)}",
                            "removed": current,
                            "added": added[:500],
                        }
                    )

        schemes.append(
            normalize_scheme(
                {
                    "title": f"{DIRECTION_LABELS.get(direction, direction)}：{issue_title[:40]}",
                    "direction": direction,
                    "target_issue_ids": issue_ids,
                    "changes_summary": f"针对「{issue_title}」的{DIRECTION_LABELS.get(direction, direction)}改法",
                    "rationale": f"基于 Expert 分析，{user_message[:120] if user_message else '在冲突点上给出可选路径'}",
                    "tradeoffs": {
                        "brand": "品牌一致性" if direction == "conservative" else "适度让步",
                        "audience": "接受度提升" if direction == "audience_friendly" else "需测试反应",
                        "creator": "表达空间" if direction == "creator_led" else "创作约束",
                    },
                    "sacrifice": "可能削弱部分品牌硬性露出" if direction != "conservative" else "创意自由度略降",
                    "communication_scene": "品牌方脚本评审会议",
                    "brand_objection": "品牌信息不够突出" if direction != "conservative" else "节奏偏保守",
                    "response_script": "我们保留了可核对的品牌锚点，同时用叙事降低广告感。",
                    "risk": "观众仍可能感知为广告" if direction == "conservative" else "品牌方或要求加戏",
                    "hunks": hunks,
                    "related_node_ids": issue_ids,
                },
                project_id=project_id,
                script_version_id=script_version_id,
                script=script,
            )
        )

    return schemes


async def run_expert_for_brief(
    project: dict[str, Any],
    brand_result: dict[str, Any],
) -> dict[str, Any]:
    context = build_agent_context("expert", project)
    assert_context_isolation("expert", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    await domain_case_retriever(topic=context.get("brief_summary", ""), mock=True)
    kb = await script_structure_kb(query="brief_initial", mock=True)

    brand_issue_ids = [
        n["node_id"] for n in brand_result.get("proposed_nodes", []) if n.get("node_type") == "issue"
    ]
    log_step("expert_agent.brief_initial", phase="IN", project_id=project_id, brand_issue_ids=brand_issue_ids)
    context_block = "\n\n".join(
        [
            f"## 场景\nbrief_initial — 为 Brand issue 补 position/argument",
            f"## Brief 摘要\n{context.get('brief_summary', '')}",
            f"## Brand 结构化结果\n{perspective_result_json(brand_result)}",
            f"## 本轮 Brand issue node_id\n{brand_issue_ids}",
            f"## 知识库结构建议\n{kb.get('patterns', [])}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        external = [
            {"from_index": 0, "to_node_id": nid, "relation_type": "responds_to"} for nid in brand_issue_ids[:1]
        ]
        return {
            "brief_impact_summary": "Brief 约束需在脚本中对齐",
            "creation_constraints": brand_result.get("constraints") or [],
            "strategy_notes": kb.get("patterns", []),
            "recommended_directions": ["balanced", "creator_led"],
            "ibis": {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "品牌合规立场",
                        "content": "满足 Brief 同时保留创作者表达空间。",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    },
                    {
                        "node_type": "argument",
                        "title": "结构建议",
                        "content": "；".join(kb.get("patterns", [])[:2]) or "节奏先松后紧",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    },
                ],
                "edges": [{"from_index": 1, "to_index": 0, "relation_type": "supports"}],
                "external_edges": external,
            },
        }

    payload = await invoke_agent_json(
        agent_prompt_file="expert_agent.md",
        context=context_block,
        task_type="expert_generate_suggestions",
        mock_payload=mock,
    )
    graph = persist_rationale_graph(
        project_id,
        payload.get("ibis"),
        script_version_id=script_version_id,
        allowed_source_types=EXPERT_SOURCES,
    )

    result = {
        "brief_impact_summary": payload.get("brief_impact_summary", ""),
        "creation_constraints": payload.get("creation_constraints") or brand_result.get("constraints") or [],
        "strategy_notes": payload.get("strategy_notes") or kb.get("patterns", []),
        "recommended_directions": payload.get("recommended_directions") or ["balanced"],
        "modification_schemes": [],
        "negotiation_preparation": None,
        "proposed_nodes": graph.proposed_nodes,
        "proposed_edges": graph.proposed_edges,
        "node_updates": graph.node_updates,
        "tool_calls_used": ["domain_case_retriever", "script_structure_kb", "persist_rationale_graph"],
    }
    log_step(
        "expert_agent.brief_initial",
        phase="OUT",
        project_id=project_id,
        proposed_nodes=len(result["proposed_nodes"]),
    )
    return result


async def run_expert_for_audience(
    project: dict[str, Any],
    audience_result: dict[str, Any],
) -> dict[str, Any]:
    context = build_agent_context("expert", project)
    assert_context_isolation("expert", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")

    audience_issue_ids = [
        n["node_id"] for n in audience_result.get("proposed_nodes", []) if n.get("node_type") == "issue"
    ]
    log_step(
        "expert_agent.audience_persona",
        phase="IN",
        project_id=project_id,
        audience_issue_ids=audience_issue_ids,
    )
    context_block = "\n\n".join(
        [
            f"## 场景\naudience_persona — 为 Audience issue 补 position/argument",
            f"## Audience 结构化结果\n{perspective_result_json(audience_result)}",
            f"## 本轮 Audience issue node_id\n{audience_issue_ids}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        external = [
            {"from_index": 0, "to_node_id": nid, "relation_type": "responds_to"} for nid in audience_issue_ids[:1]
        ]
        return {
            "strategy_notes": audience_result.get("suggestions") or [],
            "recommended_directions": ["audience_friendly"],
            "ibis": {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "观众友好表达",
                        "content": (audience_result.get("suggestions") or ["降低广告感"])[0],
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    }
                ],
                "external_edges": external,
            },
        }

    payload = await invoke_agent_json(
        agent_prompt_file="expert_agent.md",
        context=context_block,
        task_type="expert_generate_suggestions",
        mock_payload=mock,
    )
    graph = persist_rationale_graph(
        project_id,
        payload.get("ibis"),
        script_version_id=script_version_id,
        allowed_source_types=EXPERT_SOURCES,
    )

    result = {
        "brief_impact_summary": context.get("brief_summary", "")[:200],
        "creation_constraints": [],
        "strategy_notes": payload.get("strategy_notes") or audience_result.get("suggestions") or [],
        "recommended_directions": payload.get("recommended_directions") or ["audience_friendly"],
        "modification_schemes": [],
        "negotiation_preparation": None,
        "proposed_nodes": graph.proposed_nodes,
        "proposed_edges": graph.proposed_edges,
        "node_updates": graph.node_updates,
        "tool_calls_used": ["persist_rationale_graph"],
    }
    log_step(
        "expert_agent.audience_persona",
        phase="OUT",
        project_id=project_id,
        proposed_nodes=len(result["proposed_nodes"]),
    )
    return result


async def run_expert_coordinator(
    project: dict[str, Any],
    *,
    brand_result: dict[str, Any] | None = None,
    audience_result: dict[str, Any] | None = None,
    user_message: str | None = None,
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
    expert_only: bool = False,
) -> dict[str, Any]:
    context = build_agent_context("expert", project)
    assert_context_isolation("expert", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")

    row_ids = set(changed_row_ids or [])
    if quotes:
        for q in quotes:
            if q.get("row_id"):
                row_ids.add(str(q["row_id"]))

    new_issue_ids = []
    for result in (brand_result, audience_result):
        if result:
            new_issue_ids.extend(
                n["node_id"] for n in result.get("proposed_nodes", []) if n.get("node_type") == "issue"
            )

    log_step(
        "expert_agent.coordinator",
        phase="IN",
        project_id=project_id,
        expert_only=expert_only,
        user_message=user_message,
        new_issue_ids=new_issue_ids,
    )
    context_block = "\n\n".join(
        [
            f"## 场景\ncoordinator — {'Expert 单独分析' if expert_only else '综合 Expert 补图'}",
            f"## 用户问题\n{user_message or ''}",
            f"## Quotes\n{format_quotes(quotes)}",
            f"## 脚本变动/选段\n{script_excerpt_for_rows(project, row_ids) if row_ids else context.get('script_excerpt', '')}",
            f"## Brand 结果摘要\n{json.dumps(brand_result, ensure_ascii=False)[:800] if brand_result else '无'}",
            f"## Audience 结果摘要\n{json.dumps(audience_result, ensure_ascii=False)[:800] if audience_result else '无'}",
            f"## 本轮新 issue ids\n{new_issue_ids}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        question = user_message or "脚本分析"
        if expert_only and not new_issue_ids:
            return {
                "assistant_reply": f"已分析：{question[:80]}。请查看 Node Graph。",
                "strategy_notes": ["尊重创作者主导权"],
                "recommended_directions": ["balanced"],
                "ibis": {
                    "nodes": [
                        {
                            "node_type": "issue",
                            "title": f"关于「{question[:40]}」的策略分歧",
                            "content": question[:200],
                            "source_type": "expert_strategy",
                            "source_perspective": "expert",
                        },
                        {
                            "node_type": "position",
                            "title": "平衡创作者与品牌/观众",
                            "content": "在冲突点上给出可执行的折中方向。",
                            "source_type": "expert_strategy",
                            "source_perspective": "expert",
                        },
                    ],
                    "edges": [{"from_index": 1, "to_index": 0, "relation_type": "responds_to"}],
                },
            }
        external = [
            {"from_index": 0, "to_node_id": nid, "relation_type": "responds_to"} for nid in new_issue_ids[:1]
        ]
        return {
            "assistant_reply": f"已综合 Expert 视角：{question[:80]}。请查看 Node Graph。",
            "strategy_notes": ["尊重创作者主导权"],
            "recommended_directions": ["balanced"],
            "ibis": {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "平衡创作者与品牌/观众",
                        "content": "在冲突点上给出可执行的折中方向。",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    }
                ],
                "external_edges": external,
            },
        }

    payload = await invoke_agent_json(
        agent_prompt_file="expert_agent.md",
        context=context_block,
        task_type="expert_generate_suggestions",
        mock_payload=mock,
    )
    graph = persist_rationale_graph(
        project_id,
        payload.get("ibis"),
        script_version_id=script_version_id,
        allowed_source_types=EXPERT_SOURCES,
    )

    result = {
        "assistant_reply": payload.get("assistant_reply", ""),
        "strategy_notes": payload.get("strategy_notes") or [],
        "recommended_directions": payload.get("recommended_directions") or [],
        "proposed_nodes": graph.proposed_nodes,
        "proposed_edges": graph.proposed_edges,
        "node_updates": graph.node_updates,
        "tool_calls_used": ["persist_rationale_graph"],
    }
    log_step(
        "expert_agent.coordinator",
        phase="OUT",
        project_id=project_id,
        proposed_nodes=len(result["proposed_nodes"]),
        assistant_reply=result["assistant_reply"][:500],
    )
    return result


async def run_expert_generate_modification_schemes(
    project: dict[str, Any],
    *,
    target_issue_ids: list[str] | None = None,
    user_message: str | None = None,
) -> dict[str, Any]:
    context = build_agent_context("expert", project)
    assert_context_isolation("expert", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    target_issues = _pick_target_issues(project, target_issue_ids)

    log_step(
        "expert_agent.generate_schemes",
        phase="IN",
        project_id=project_id,
        target_issue_ids=[n.get("node_id") for n in target_issues],
    )

    issues_block = "\n".join(
        f"- {n.get('node_id')}: {n.get('title', '')} | {str(n.get('content', ''))[:120]}"
        for n in target_issues
    ) or "（无明确 issue，请基于脚本与图整体给方案）"

    context_block = "\n\n".join(
        [
            "## 场景\ngenerate_modification_schemes — 为冲突 issue 生成至少 2 个不同方向的修改方案",
            f"## 用户说明\n{user_message or '请针对待协商/开放 issue 给出多方向修改方案'}",
            f"## 目标 Issue\n{issues_block}",
            f"## 脚本摘要\n{context.get('script_excerpt', '')[:1200]}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        schemes = _mock_modification_schemes(
            project,
            target_issues=target_issues,
            user_message=user_message,
        )
        return {
            "assistant_reply": f"已生成 {len(schemes)} 个不同方向的修改方案，请在 Revision Proposals 中查看与应用。",
            "modification_schemes": schemes,
        }

    payload = await invoke_agent_json(
        agent_prompt_file="expert_agent.md",
        context=context_block,
        task_type="expert_generate_hunks",
        mock_payload=mock,
    )
    # Modification-scheme flow must not create IBIS nodes.
    payload.pop("ibis", None)

    script = project.get("current_script") or {}
    schemes = [
        normalize_scheme(
            item,
            project_id=project_id,
            script_version_id=script_version_id,
            script=script,
        )
        for item in (payload.get("modification_schemes") or [])
        if isinstance(item, dict)
    ]
    if len(schemes) < 2:
        schemes = _mock_modification_schemes(
            project,
            target_issues=target_issues,
            user_message=user_message,
        )

    result = {
        "assistant_reply": payload.get("assistant_reply", ""),
        "modification_schemes": schemes,
        "tool_calls_used": ["modification_scheme_writer"],
    }
    log_step(
        "expert_agent.generate_schemes",
        phase="OUT",
        project_id=project_id,
        scheme_count=len(schemes),
    )
    return result
