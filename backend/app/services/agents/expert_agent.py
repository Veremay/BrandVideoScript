from __future__ import annotations

import json
from typing import Any

from app.services.agent_context import assert_context_isolation, build_agent_context
from app.services.agent_llm import (
    existing_nodes_summary,
    format_quotes,
    invoke_agent_json,
    perspective_result_json,
    format_script_for_prompt,
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


def _issues_for_positions(
    project: dict[str, Any],
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not positions:
        return []
    nodes_by_id = {n.get("node_id"): n for n in (project.get("rationale_nodes") or []) if n.get("node_id")}
    issue_ids: list[str] = []
    for edge in project.get("rationale_edges") or []:
        if edge.get("relation_type") != "responds_to":
            continue
        position_id = edge.get("from_node_id")
        issue_id = edge.get("to_node_id")
        if position_id in {p.get("node_id") for p in positions} and issue_id:
            issue_ids.append(str(issue_id))
    seen: set[str] = set()
    issues: list[dict[str, Any]] = []
    for issue_id in issue_ids:
        if issue_id in seen:
            continue
        seen.add(issue_id)
        issue = nodes_by_id.get(issue_id)
        if issue and issue.get("node_type") == "issue":
            issues.append(issue)
    return issues


def _pick_target_positions(
    project: dict[str, Any],
    target_position_ids: list[str] | None,
) -> list[dict[str, Any]]:
    nodes = project.get("rationale_nodes") or []
    positions = [n for n in nodes if n.get("node_type") == "position"]
    if target_position_ids:
        wanted = set(target_position_ids)
        filtered = [n for n in positions if n.get("node_id") in wanted]
        return filtered or positions[:3]
    queue = set(project.get("consideration_queue") or [])
    prioritized = [
        n
        for n in positions
        if n.get("in_consideration_queue") or n.get("node_id") in queue or n.get("status") == "to_be_considered"
    ]
    return prioritized[:5] or positions[:2]


def _pick_target_issues(
    project: dict[str, Any],
    target_issue_ids: list[str] | None,
    *,
    target_positions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if target_positions:
        linked = _issues_for_positions(project, target_positions)
        if linked:
            return linked
    nodes = project.get("rationale_nodes") or []
    issues = [n for n in nodes if n.get("node_type") == "issue"]
    if target_issue_ids:
        wanted = set(target_issue_ids)
        filtered = [n for n in issues if n.get("node_id") in wanted]
        return filtered or issues[:3]
    prioritized = [n for n in issues if n.get("status") in {"open", "in_review"}]
    return prioritized[:3] or issues[:2]


def _mock_modification_schemes(
    project: dict[str, Any],
    *,
    target_issues: list[dict[str, Any]],
    target_positions: list[dict[str, Any]] | None = None,
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
    position_ids = [n["node_id"] for n in (target_positions or []) if n.get("node_id")]
    position_title = (target_positions or [{}])[0].get("title", "") if target_positions else ""
    issue_title = position_title or (target_issues[0].get("title", "脚本冲突") if target_issues else "整体脚本")

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

    for direction in directions[:1]:
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
                    "target_position_ids": position_ids,
                    "changes_summary": f"落实立场「{issue_title}」的{DIRECTION_LABELS.get(direction, direction)}改法",
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
                    "related_node_ids": [*position_ids, *issue_ids],
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

    brand_position_ids = [
        n["node_id"] for n in brand_result.get("proposed_nodes", []) if n.get("node_type") == "position"
    ]
    log_step(
        "expert_agent.brief_initial",
        phase="IN",
        project_id=project_id,
        brand_position_ids=brand_position_ids,
    )
    context_block = "\n\n".join(
        [
            f"## 场景\nbrief_initial — 在品牌 position 与创作立场之间识别冲突，派生 issue",
            f"## Brief 摘要\n{context.get('brief_summary', '')}",
            f"## Brand 结构化结果\n{perspective_result_json(brand_result)}",
            f"## 本轮 Brand position node_id\n{brand_position_ids}",
            f"## 知识库结构建议\n{kb.get('patterns', [])}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        ibis: dict[str, Any] = {
            "nodes": [
                {
                    "node_type": "position",
                    "title": "创作自然性优先",
                    "content": "在满足 Brief 的同时保留叙事节奏，弱化硬广。",
                    "source_type": "expert_strategy",
                    "source_perspective": "expert",
                }
            ],
            "edges": [],
            "external_edges": [],
        }
        # ≥2 conflicting positions (brand vs expert) derive a conflict issue.
        if brand_position_ids:
            brand_pos = brand_position_ids[0]
            ibis["nodes"].append(
                {
                    "node_type": "issue",
                    "title": "品牌露出强度 vs 内容自然性",
                    "content": "品牌诉求与创作自然性立场冲突，待权衡。",
                    "source_type": "expert_strategy",
                    "source_perspective": "expert",
                }
            )
            ibis["edges"].append({"from_index": 0, "to_index": 1, "relation_type": "responds_to"})
            ibis["external_edges"].extend(
                [
                    {"from_node_id": brand_pos, "to_index": 1, "relation_type": "responds_to"},
                    {"from_node_id": brand_pos, "to_index": 0, "relation_type": "conflicts_with"},
                ]
            )
        return {
            "brief_impact_summary": "Brief 约束需在脚本中对齐",
            "creation_constraints": brand_result.get("constraints") or [],
            "strategy_notes": kb.get("patterns", []),
            "recommended_directions": ["balanced", "creator_led"],
            "ibis": ibis,
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

    audience_position_ids = [
        n["node_id"] for n in audience_result.get("proposed_nodes", []) if n.get("node_type") == "position"
    ]
    existing_position_ids = [
        str(n.get("node_id"))
        for n in project.get("rationale_nodes", [])
        if n.get("node_type") == "position" and n.get("node_id")
    ]
    log_step(
        "expert_agent.audience_persona",
        phase="IN",
        project_id=project_id,
        audience_position_ids=audience_position_ids,
    )
    context_block = "\n\n".join(
        [
            f"## 场景\naudience_persona — 在观众 position 与其它立场之间识别冲突，派生 issue",
            f"## Audience 结构化结果\n{perspective_result_json(audience_result)}",
            f"## 本轮 Audience position node_id\n{audience_position_ids}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        ibis: dict[str, Any] = {"nodes": [], "edges": [], "external_edges": []}
        # Prefer an audience-vs-existing conflict; otherwise add an expert position to conflict with.
        counter_position_id = existing_position_ids[0] if existing_position_ids else None
        if audience_position_ids:
            audience_pos = audience_position_ids[0]
            if counter_position_id is None:
                ibis["nodes"].append(
                    {
                        "node_type": "position",
                        "title": "品牌露出优先",
                        "content": "确保品牌核心信息清晰呈现。",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    }
                )
                ibis["nodes"].append(
                    {
                        "node_type": "issue",
                        "title": "广告感 vs 品牌露出",
                        "content": "观众友好立场与品牌露出立场冲突。",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    }
                )
                ibis["edges"].append({"from_index": 0, "to_index": 1, "relation_type": "responds_to"})
                ibis["external_edges"].extend(
                    [
                        {"from_node_id": audience_pos, "to_index": 1, "relation_type": "responds_to"},
                        {"from_node_id": audience_pos, "to_index": 0, "relation_type": "conflicts_with"},
                    ]
                )
            else:
                ibis["nodes"].append(
                    {
                        "node_type": "issue",
                        "title": "广告感 vs 品牌露出",
                        "content": "观众友好立场与已有立场冲突。",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    }
                )
                ibis["external_edges"].extend(
                    [
                        {"from_node_id": audience_pos, "to_index": 0, "relation_type": "responds_to"},
                        {"from_node_id": counter_position_id, "to_index": 0, "relation_type": "responds_to"},
                        {"from_node_id": audience_pos, "to_node_id": counter_position_id, "relation_type": "conflicts_with"},
                    ]
                )
        return {
            "strategy_notes": audience_result.get("suggestions") or [],
            "recommended_directions": ["audience_friendly"],
            "ibis": ibis,
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

    new_position_ids: list[str] = []
    for result in (brand_result, audience_result):
        if result:
            new_position_ids.extend(
                n["node_id"] for n in result.get("proposed_nodes", []) if n.get("node_type") == "position"
            )
    existing_position_ids = [
        str(n.get("node_id"))
        for n in project.get("rationale_nodes", [])
        if n.get("node_type") == "position" and n.get("node_id")
    ]
    # Positions available for conflict detection: this round's first, then prior graph.
    candidate_position_ids = list(dict.fromkeys([*new_position_ids, *existing_position_ids]))

    log_step(
        "expert_agent.coordinator",
        phase="IN",
        project_id=project_id,
        expert_only=expert_only,
        user_message=user_message,
        candidate_position_ids=candidate_position_ids,
    )
    context_block = "\n\n".join(
        [
            f"## 场景\ncoordinator — {'Expert 单独分析' if expert_only else '综合各方 position 识别冲突'}",
            f"## 用户问题\n{user_message or ''}",
            f"## Quotes\n{format_quotes(quotes)}",
            f"## 脚本变动/选段\n{script_excerpt_for_rows(project, row_ids) if row_ids else context.get('script_excerpt', '')}",
            f"## Brand 结果摘要\n{json.dumps(brand_result, ensure_ascii=False)[:800] if brand_result else '无'}",
            f"## Audience 结果摘要\n{json.dumps(audience_result, ensure_ascii=False)[:800] if audience_result else '无'}",
            f"## 可用于冲突判定的 position ids\n{candidate_position_ids}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        question = user_message or "脚本分析"
        reply = (
            f"已分析：{question[:80]}。请查看 Node Graph。"
            if expert_only
            else f"已综合 Expert 视角：{question[:80]}。请查看 Node Graph。"
        )
        ibis: dict[str, Any] = {"nodes": [], "edges": [], "external_edges": []}
        if len(candidate_position_ids) >= 2:
            # Two existing positions conflict -> derive a conflict issue.
            pos_a, pos_b = candidate_position_ids[0], candidate_position_ids[1]
            ibis["nodes"].append(
                {
                    "node_type": "issue",
                    "title": f"关于「{question[:32]}」的立场冲突",
                    "content": question[:200] or "不同视角立场冲突。",
                    "source_type": "expert_strategy",
                    "source_perspective": "expert",
                }
            )
            ibis["external_edges"].extend(
                [
                    {"from_node_id": pos_a, "to_index": 0, "relation_type": "responds_to"},
                    {"from_node_id": pos_b, "to_index": 0, "relation_type": "responds_to"},
                    {"from_node_id": pos_a, "to_node_id": pos_b, "relation_type": "conflicts_with"},
                ]
            )
        elif len(candidate_position_ids) == 1:
            # Only one stance so far: add an expert counter-position and form the conflict.
            ibis["nodes"].extend(
                [
                    {
                        "node_type": "position",
                        "title": "平衡创作者与品牌/观众",
                        "content": "在冲突点上给出可执行的折中方向。",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    },
                    {
                        "node_type": "issue",
                        "title": f"关于「{question[:32]}」的立场冲突",
                        "content": question[:200] or "不同视角立场冲突。",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    },
                ]
            )
            ibis["edges"].append({"from_index": 0, "to_index": 1, "relation_type": "responds_to"})
            ibis["external_edges"].extend(
                [
                    {"from_node_id": candidate_position_ids[0], "to_index": 1, "relation_type": "responds_to"},
                    {"from_node_id": candidate_position_ids[0], "to_index": 0, "relation_type": "conflicts_with"},
                ]
            )
        else:
            # No positions anywhere: contribute a standalone expert position (a root).
            ibis["nodes"].append(
                {
                    "node_type": "position",
                    "title": "平衡创作者与品牌/观众",
                    "content": "在冲突点上给出可执行的折中方向。",
                    "source_type": "expert_strategy",
                    "source_perspective": "expert",
                }
            )
        return {
            "assistant_reply": reply,
            "strategy_notes": ["尊重创作者主导权"],
            "recommended_directions": ["balanced"],
            "ibis": ibis,
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


async def run_expert_populate_issue(
    project: dict[str, Any],
    issue: dict[str, Any],
) -> dict[str, Any]:
    """Organize ≥2 conflicting Positions around a user-created Issue.

    Bottom-up IBIS treats an Issue as a conflict, so when a creator drops an Issue
    on the canvas the Expert fills in the opposing stances that make the conflict
    concrete (responds_to the issue + conflicts_with each other).
    """
    context = build_agent_context("expert", project)
    assert_context_isolation("expert", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    issue_id = str(issue.get("node_id") or "")
    issue_title = str(issue.get("title") or "")
    issue_content = str(issue.get("content") or "")

    log_step(
        "expert_agent.populate_issue",
        phase="IN",
        project_id=project_id,
        issue_id=issue_id,
        issue_title=issue_title,
    )
    context_block = "\n\n".join(
        [
            "## 场景\npopulate_issue — 为用户创建的 issue 组织 ≥2 个相互冲突的 position",
            f"## 目标 Issue\nid={issue_id}\n标题：{issue_title}\n内容：{issue_content}",
            f"## 脚本摘要\n{context.get('script_excerpt', '')}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
            "## 要求\n输出至少 2 个相互对立的 position：用 external_edges 将每个 position（from_index）"
            f"以 responds_to 连到该 issue（to_node_id={issue_id}），并在两个 position 间补 conflicts_with。",
        ]
    )

    def mock() -> dict[str, Any]:
        label = issue_title[:30] or "该议题"
        return {
            "assistant_reply": f"已围绕「{label}」组织对立立场，请查看 Node Graph。",
            "ibis": {
                "nodes": [
                    {
                        "node_type": "position",
                        "title": "偏品牌 / 保守立场",
                        "content": f"针对「{label}」更偏向满足品牌诉求与露出。",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    },
                    {
                        "node_type": "position",
                        "title": "偏创作 / 观众立场",
                        "content": f"针对「{label}」更偏向创作自然性与观众体验。",
                        "source_type": "expert_strategy",
                        "source_perspective": "expert",
                    },
                ],
                "edges": [{"from_index": 0, "to_index": 1, "relation_type": "conflicts_with"}],
                "external_edges": [
                    {"from_index": 0, "to_node_id": issue_id, "relation_type": "responds_to"},
                    {"from_index": 1, "to_node_id": issue_id, "relation_type": "responds_to"},
                ],
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
        "proposed_nodes": graph.proposed_nodes,
        "proposed_edges": graph.proposed_edges,
        "node_updates": graph.node_updates,
        "tool_calls_used": ["persist_rationale_graph"],
    }
    log_step(
        "expert_agent.populate_issue",
        phase="OUT",
        project_id=project_id,
        proposed_nodes=len(result["proposed_nodes"]),
    )
    return result


def _anchored_issue_summaries(project: dict[str, Any]) -> list[dict[str, Any]]:
    """Existing Issues (active + resolved) with the Positions that respond to them.

    This is the anchor set fed to the Expert on "update map": each Issue keeps its
    id so verdicts (still_holds / resolved / modified) map back to the live node.
    """
    nodes_by_id = {n.get("node_id"): n for n in (project.get("rationale_nodes") or []) if n.get("node_id")}
    issue_positions: dict[str, list[str]] = {}
    for edge in project.get("rationale_edges") or []:
        if edge.get("relation_type") != "responds_to":
            continue
        issue_id = str(edge.get("to_node_id") or "")
        pos_id = str(edge.get("from_node_id") or "")
        if issue_id and pos_id:
            issue_positions.setdefault(issue_id, []).append(pos_id)

    summaries: list[dict[str, Any]] = []
    for node in nodes_by_id.values():
        if node.get("node_type") != "issue":
            continue
        if node.get("lifecycle", "active") not in {"active", "resolved"}:
            continue
        positions = [
            {
                "position_id": pid,
                "title": str(nodes_by_id.get(pid, {}).get("title", "")),
                "content": str(nodes_by_id.get(pid, {}).get("content", ""))[:200],
            }
            for pid in issue_positions.get(str(node.get("node_id")), [])
            if nodes_by_id.get(pid)
        ]
        summaries.append(
            {
                "issue_id": str(node.get("node_id")),
                "title": str(node.get("title", "")),
                "content": str(node.get("content", ""))[:200],
                "lifecycle": node.get("lifecycle", "active"),
                "created_by": node.get("created_by", "agent"),
                "positions": positions,
            }
        )
    return summaries


async def run_expert_reconcile(
    project: dict[str, Any],
    *,
    changed_row_ids: set[str] | None = None,
    user_message: str | None = None,
) -> dict[str, Any]:
    """Anchored re-evaluation for "update map".

    For every existing Issue the Expert returns a verdict — ``still_holds`` /
    ``resolved`` (conflict gone) / ``modified`` (conflict reframed) — plus any
    Position/Argument content that changed substantively, plus brand-new
    conflicts. Ids are preserved; the merge layer turns ``modified`` into a
    supersede and ``resolved`` into a dimmed node.
    """
    context = build_agent_context("expert", project)
    assert_context_isolation("expert", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    row_ids = set(changed_row_ids or [])

    anchored_issues = _anchored_issue_summaries(project)
    existing_positions = [
        {
            "position_id": str(n.get("node_id")),
            "title": str(n.get("title", "")),
            "content": str(n.get("content", ""))[:200],
            "created_by": n.get("created_by", "agent"),
        }
        for n in project.get("rationale_nodes", [])
        if n.get("node_type") == "position" and n.get("node_id") and n.get("lifecycle", "active") == "active"
    ]

    log_step(
        "expert_agent.reconcile",
        phase="IN",
        project_id=project_id,
        anchored_issue_ids=[i["issue_id"] for i in anchored_issues],
        changed_row_ids=sorted(row_ids),
    )

    context_block = "\n\n".join(
        [
            "## 场景\nreconcile（update map）— 对每个已有 issue 重新判定冲突是否仍成立",
            f"## 用户说明\n{user_message or '脚本已更新，请重新评估各冲突'}",
            f"## 脚本变动/选段\n{script_excerpt_for_rows(project, row_ids) if row_ids else context.get('script_excerpt', '')}",
            f"## 待复评的 Issue（含其立场，issue_id 必须原样回传）\n{json.dumps(anchored_issues, ensure_ascii=False)[:3000]}",
            f"## 现有 position（可用于判断与新建冲突）\n{json.dumps(existing_positions, ensure_ascii=False)[:2000]}",
            (
                "## 输出要求\n"
                "1) issue_reviews：对上面每个 issue 给出 {issue_id, verdict, reason}；"
                "verdict ∈ still_holds | resolved | modified；"
                "默认 still_holds，只有冲突确实消失才 resolved，只有冲突实质改变才 modified"
                "（modified 时附 new_title / new_content）。\n"
                "2) node_modifications：仅当某个 position/argument 内容发生实质变化时，"
                "给出 {node_id, new_title, new_content, reason}。\n"
                "3) ibis：仅放【全新】冲突（≥2 个对立 position + 一个 issue，"
                "用 responds_to / conflicts_with 连接；可用 external_edges 接现有 position）。\n"
                "不要改动 created_by=user 的节点，只在必要时通过 reason 说明。"
            ),
        ]
    )

    def mock() -> dict[str, Any]:
        return {
            "assistant_reply": "已重新评估各冲突，未发现实质变化。请查看 Node Graph。",
            "issue_reviews": [
                {"issue_id": item["issue_id"], "verdict": "still_holds"} for item in anchored_issues
            ],
            "node_modifications": [],
            "ibis": {"nodes": [], "edges": [], "external_edges": []},
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

    anchored_ids = {item["issue_id"] for item in anchored_issues}
    issue_reviews = [
        review
        for review in (payload.get("issue_reviews") or [])
        if isinstance(review, dict) and str(review.get("issue_id") or "") in anchored_ids
    ]
    node_modifications = [
        mod
        for mod in (payload.get("node_modifications") or [])
        if isinstance(mod, dict) and mod.get("node_id")
    ]

    result = {
        "assistant_reply": payload.get("assistant_reply", ""),
        "issue_reviews": issue_reviews,
        "node_modifications": node_modifications,
        "proposed_nodes": graph.proposed_nodes,
        "proposed_edges": graph.proposed_edges,
        "node_updates": [],
        "tool_calls_used": ["persist_rationale_graph"],
    }
    log_step(
        "expert_agent.reconcile",
        phase="OUT",
        project_id=project_id,
        issue_reviews=len(issue_reviews),
        node_modifications=len(node_modifications),
        new_nodes=len(graph.proposed_nodes),
    )
    return result


async def run_expert_generate_modification_schemes(
    project: dict[str, Any],
    *,
    target_issue_ids: list[str] | None = None,
    target_position_ids: list[str] | None = None,
    user_message: str | None = None,
) -> dict[str, Any]:
    context = build_agent_context("expert", project)
    assert_context_isolation("expert", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    target_positions = _pick_target_positions(project, target_position_ids)
    target_issues = _pick_target_issues(
        project,
        target_issue_ids,
        target_positions=target_positions,
    )

    log_step(
        "expert_agent.generate_schemes",
        phase="IN",
        project_id=project_id,
        target_position_ids=[n.get("node_id") for n in target_positions],
        target_issue_ids=[n.get("node_id") for n in target_issues],
    )

    positions_block = "\n".join(
        f"- {n.get('node_id')}: {n.get('title', '')} | {str(n.get('content', ''))[:120]}"
        for n in target_positions
    ) or "（无采纳立场，请基于脚本与图整体给方案）"
    issues_block = "\n".join(
        f"- {n.get('node_id')}: {n.get('title', '')} | {str(n.get('content', ''))[:120]}"
        for n in target_issues
    ) or "（无关联 issue）"

    context_block = "\n\n".join(
        [
            "## 场景\ngenerate_modification_schemes — 为创作者采纳的 Position 生成 1 个修改方案",
            f"## 用户说明\n{user_message or '请针对 TO BE CONSIDERED 列表中的立场给出脚本修改方案'}",
            f"## 采纳的 Position\n{positions_block}",
            f"## 关联 Issue\n{issues_block}",
            f"## 当前脚本（全文，hunk 须使用下列 row_id / column_id）\n{format_script_for_prompt(project)}",
            f"## 已有节点\n{existing_nodes_summary(project)}",
        ]
    )

    def mock() -> dict[str, Any]:
        schemes = _mock_modification_schemes(
            project,
            target_issues=target_issues,
            target_positions=target_positions,
            user_message=user_message,
        )
        return {
            "assistant_reply": f"已生成 {len(schemes)} 个修改方案，请在 Script Editor 中逐条审阅 diff 并 Accept/Reject。",
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
    if not schemes:
        schemes = _mock_modification_schemes(
            project,
            target_issues=target_issues,
            target_positions=target_positions,
            user_message=user_message,
        )
    schemes = schemes[:1]

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
