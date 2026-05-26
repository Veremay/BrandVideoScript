from __future__ import annotations

import re
from typing import Any

from app.models.rationale_ops import build_rationale_edge, build_rationale_node
from app.repositories.projects import build_brand_insight
from app.services.agent_context import assert_context_isolation, build_agent_context
from app.services.tools.brand_wiki import brand_wiki_lookup
from app.services.tavily_client import TavilyClient


def _extract_brief_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[-*•\d.)\]]+\s*", "", line).strip()
        if len(line) >= 6:
            lines.append(line)
    return lines[:12]


async def run_brand_agent(project: dict[str, Any]) -> dict[str, Any]:
    context = build_agent_context("brand", project)
    assert_context_isolation("brand", context)

    brief = context.get("brief") or {}
    text = str(brief.get("text") or brief.get("summary") or "").strip()
    project_id = str(context.get("project_id") or project.get("_id") or "")
    script_version_id = context.get("current_script_version_id")

    lines = _extract_brief_lines(text)
    explicit: list[dict[str, Any]] = []
    implicit: list[dict[str, Any]] = []
    proposed_nodes: list[dict] = []
    proposed_edges: list[dict] = []
    brand_insights: list[dict] = []

    wiki = await brand_wiki_lookup(brief.get("filename"), mock=True)
    for snippet in wiki.get("snippets", []):
        implicit.append(
            {
                "text": snippet.get("text", ""),
                "evidence": f"brand_wiki:{snippet.get('topic', 'wiki')}",
                "confidence": "medium",
            }
        )

    tavily = TavilyClient()
    if text:
        search = await tavily.search(query=text[:120], max_results=2, mock=True)
        for result in search.get("results", [])[:2]:
            implicit.append(
                {
                    "text": f"公开资料提及：{result.get('title', '相关报道')}",
                    "evidence": result.get("url", "tavily"),
                    "confidence": "low",
                }
            )

    for index, line in enumerate(lines):
        explicit.append({"text": line, "evidence": line[:160], "confidence": "high"})
        issue = build_rationale_node(
            project_id=project_id,
            node_type="issue",
            title=line[:80],
            content=f"Brief 明确要求：{line}",
            source_type="brand_brief",
            source_perspective="brand",
            business_tags=["brand_requirement"],
            layout={"x": 160.0, "y": 80.0 + index * 160.0},
            based_on_script_version_id=script_version_id,
        )
        proposed_nodes.append(issue)
        brand_insights.append(
            build_brand_insight(
                category="explicit_requirement",
                title=line[:80],
                content=line,
                reason="Brief 解析识别的显式需求",
                evidence=[{"source_type": "brief", "quote": line[:200]}],
                confidence="high",
                created_by="agent",
            )
        )

    if not explicit and text:
        fallback = text[:200]
        explicit.append({"text": fallback, "evidence": fallback, "confidence": "medium"})
        issue = build_rationale_node(
            project_id=project_id,
            node_type="issue",
            title="Brief 核心诉求",
            content=fallback,
            source_type="brand_brief",
            source_perspective="brand",
            business_tags=["brand_requirement"],
            layout={"x": 160.0, "y": 120.0},
            based_on_script_version_id=script_version_id,
        )
        proposed_nodes.append(issue)

    for index, item in enumerate(implicit[:3]):
        node = build_rationale_node(
            project_id=project_id,
            node_type="issue",
            title=f"隐性需求 {index + 1}",
            content=item["text"],
            source_type="brand_inferred",
            source_perspective="brand",
            business_tags=["brand_requirement", "conflict"],
            confidence=item.get("confidence", "medium"),
            layout={"x": 160.0, "y": 80.0 + (len(explicit) + index) * 150.0},
            based_on_script_version_id=script_version_id,
        )
        proposed_nodes.append(node)
        brand_insights.append(
            build_brand_insight(
                category="implicit_requirement",
                title=node["title"],
                content=item["text"],
                reason="品牌 Wiki / 公开资料推断",
                evidence=[{"source_type": "brief", "quote": item.get("evidence", "")}],
                confidence=item.get("confidence", "medium"),
                created_by="agent",
            )
        )

    constraints = [item["text"] for item in explicit[:5]]
    if any("避免" in line or "不要" in line for line in lines):
        constraints.append("Brief 包含否定性约束，需在脚本中规避硬广表达")

    return {
        "explicit_requirements": explicit,
        "implicit_requirements": implicit,
        "constraints": constraints,
        "pr_risks": ["过度承诺功效", "口播感过强引发受众反感"],
        "proposed_nodes": proposed_nodes,
        "proposed_edges": proposed_edges,
        "brand_insights": brand_insights,
        "tool_calls_used": ["tavily_search", "brand_wiki_lookup"],
    }
