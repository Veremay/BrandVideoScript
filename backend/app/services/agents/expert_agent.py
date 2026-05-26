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
from app.services.tools.ibis_graph import persist_rationale_graph

EXPERT_SOURCES = {"expert_strategy"}


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
