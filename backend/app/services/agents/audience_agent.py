from __future__ import annotations

from typing import Any

from app.models.rationale_ops import build_rationale_node
from app.services.agent_context import assert_context_isolation, build_agent_context


async def run_audience_agent(project: dict[str, Any]) -> dict[str, Any]:
    context = build_agent_context("audience", project)
    assert_context_isolation("audience", context)

    persona = context.get("active_persona")
    if not persona:
        raise ValueError("Active persona is required for audience analysis")

    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")
    proposed_nodes: list[dict] = []
    structured_issues: list[dict[str, str]] = []

    ad_level = persona.get("ad_sensitivity", "medium")
    naturalness = f"以 {persona.get('name', '目标观众')} 视角，{'高' if ad_level == 'high' else '中' if ad_level == 'medium' else '低'}广告敏感。"
    ad_sense = f"平台语境：{persona.get('platform_context') or context.get('platform_context', 'other')}。"
    trust = "、".join(persona.get("trust_trigger") or []) or "真实体验与细节"
    reject = "、".join(persona.get("reject_trigger") or []) or "硬广话术"

    issues_data = [
        (
            "观众信任门槛",
            f"需呈现 {trust}，否则易划走。",
            "audience_persona",
        ),
        (
            "广告感风险",
            f"需规避 {reject}；当前人设对广告{'非常' if ad_level == 'high' else ''}敏感。",
            "audience_simulation",
        ),
    ]

    if context.get("script_excerpt"):
        issues_data.append(
            (
                "脚本观感初判",
                f"基于当前脚本片段：{context['script_excerpt'][:120]}…",
                "audience_simulation",
            )
        )

    for index, (title, content, source_type) in enumerate(issues_data):
        structured_issues.append({"title": title, "content": content})
        proposed_nodes.append(
            build_rationale_node(
                project_id=project_id,
                node_type="issue",
                title=title,
                content=content,
                source_type=source_type,
                source_perspective="audience",
                business_tags=["audience_feedback"],
                layout={"x": 180.0, "y": 100.0 + index * 170.0},
                based_on_script_version_id=script_version_id,
            )
        )

    return {
        "naturalness": naturalness,
        "ad_sense": ad_sense,
        "trust": trust,
        "drop_off_risk": reject,
        "suggestions": [
            "开头 3 秒点明对观众的价值",
            "用生活场景替代功能堆砌",
        ],
        "structured_issues": structured_issues,
        "proposed_nodes": proposed_nodes,
        "proposed_edges": [],
    }
