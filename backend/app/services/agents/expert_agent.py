from __future__ import annotations

from typing import Any

from app.models.rationale_ops import build_rationale_edge, build_rationale_node
from app.services.agent_context import assert_context_isolation, build_agent_context
from app.services.tools.expert_kb import domain_case_retriever, script_structure_kb


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

    proposed_nodes: list[dict] = list(brand_result.get("proposed_nodes") or [])
    proposed_edges: list[dict] = list(brand_result.get("proposed_edges") or [])

    issue_nodes = [node for node in proposed_nodes if node.get("node_type") == "issue"]
    for index, issue in enumerate(issue_nodes):
        position = build_rationale_node(
            project_id=project_id,
            node_type="position",
            title="品牌合规立场",
            content="在满足 Brief 约束的前提下，保留创作者表达空间。",
            source_type="expert_strategy",
            source_perspective="expert",
            business_tags=["revision_option"],
            layout={"x": 520.0, "y": issue.get("layout", {}).get("y", 120.0)},
            based_on_script_version_id=script_version_id,
        )
        argument = build_rationale_node(
            project_id=project_id,
            node_type="argument",
            title="结构建议",
            content="；".join(kb.get("patterns", [])[:2]),
            source_type="expert_strategy",
            source_perspective="expert",
            layout={"x": 900.0, "y": position["layout"]["y"] + 20.0},
            based_on_script_version_id=script_version_id,
        )
        proposed_nodes.extend([position, argument])
        # Graph layout: Issue (left) → Position → Argument (React Flow source→target)
        proposed_edges.append(
            build_rationale_edge(
                project_id=project_id,
                from_node_id=issue["node_id"],
                to_node_id=position["node_id"],
                relation_type="responds_to",
            )
        )
        proposed_edges.append(
            build_rationale_edge(
                project_id=project_id,
                from_node_id=position["node_id"],
                to_node_id=argument["node_id"],
                relation_type="supports",
            )
        )

    explicit_count = len(brand_result.get("explicit_requirements") or [])
    return {
        "brief_impact_summary": f"Brief 带来 {explicit_count} 条显式约束，需在脚本节奏与表达上对齐品牌要求。",
        "creation_constraints": brand_result.get("constraints") or [],
        "strategy_notes": kb.get("patterns", []),
        "recommended_directions": ["balanced", "creator_led"],
        "modification_schemes": [],
        "negotiation_preparation": None,
        "proposed_nodes": proposed_nodes,
        "proposed_edges": proposed_edges,
        "tool_calls_used": ["domain_case_retriever", "script_structure_kb"],
    }


async def run_expert_for_audience(
    project: dict[str, Any],
    audience_result: dict[str, Any],
) -> dict[str, Any]:
    context = build_agent_context("expert", project)
    assert_context_isolation("expert", context)

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    proposed_nodes: list[dict] = list(audience_result.get("proposed_nodes") or [])
    proposed_edges: list[dict] = list(audience_result.get("proposed_edges") or [])

    for index, issue in enumerate([n for n in proposed_nodes if n.get("node_type") == "issue"]):
        position = build_rationale_node(
            project_id=project_id,
            node_type="position",
            title="观众友好表达",
            content=audience_result.get("suggestions", ["降低广告感"])[0],
            source_type="expert_strategy",
            source_perspective="expert",
            business_tags=["audience_feedback"],
            layout={"x": 520.0, "y": issue.get("layout", {}).get("y", 100.0 + index * 40)},
            based_on_script_version_id=script_version_id,
        )
        proposed_edges.append(
            build_rationale_edge(
                project_id=project_id,
                from_node_id=issue["node_id"],
                to_node_id=position["node_id"],
                relation_type="responds_to",
            )
        )
        proposed_nodes.append(position)

    return {
        "brief_impact_summary": context.get("brief_summary", "")[:200],
        "creation_constraints": [],
        "strategy_notes": audience_result.get("suggestions", []),
        "recommended_directions": ["audience_friendly", "creator_led"],
        "modification_schemes": [],
        "negotiation_preparation": None,
        "proposed_nodes": proposed_nodes,
        "proposed_edges": proposed_edges,
        "tool_calls_used": ["script_structure_kb"],
    }
