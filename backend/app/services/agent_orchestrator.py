from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.agents.audience_agent import run_audience_agent
from app.services.agents.brand_agent import run_brand_agent
from app.services.agents.expert_agent import (
    run_expert_coordinator,
    run_expert_for_audience,
    run_expert_for_brief,
)
from app.services.tools.ibis_graph import apply_node_updates


@dataclass
class AgentPipelineResult:
    proposed_nodes: list[dict[str, Any]] = field(default_factory=list)
    proposed_edges: list[dict[str, Any]] = field(default_factory=list)
    node_updates: list[dict[str, Any]] = field(default_factory=list)
    assistant_reply: str = ""
    brand_result: dict[str, Any] | None = None
    audience_result: dict[str, Any] | None = None
    expert_result: dict[str, Any] | None = None


def _extend_graph(result: AgentPipelineResult, agent_output: dict[str, Any]) -> None:
    result.proposed_nodes.extend(agent_output.get("proposed_nodes") or [])
    result.proposed_edges.extend(agent_output.get("proposed_edges") or [])
    result.node_updates.extend(agent_output.get("node_updates") or [])


async def run_brief_initial_pipeline(project: dict[str, Any]) -> AgentPipelineResult:
    """Brand Agent → Expert Agent；图节点经 persist_rationale_graph 工具落库。"""
    pipeline = AgentPipelineResult()
    brand_result = await run_brand_agent(project)
    pipeline.brand_result = brand_result
    _extend_graph(pipeline, brand_result)

    expert_result = await run_expert_for_brief(project, brand_result)
    pipeline.expert_result = expert_result
    _extend_graph(pipeline, expert_result)
    return pipeline


async def run_audience_pipeline(project: dict[str, Any]) -> AgentPipelineResult:
    """Audience Agent → Expert Agent。"""
    pipeline = AgentPipelineResult()
    audience_result = await run_audience_agent(project)
    pipeline.audience_result = audience_result
    _extend_graph(pipeline, audience_result)

    expert_result = await run_expert_for_audience(project, audience_result)
    pipeline.expert_result = expert_result
    _extend_graph(pipeline, expert_result)
    return pipeline


async def run_coordinator_pipeline(
    project: dict[str, Any],
    *,
    perspectives: set[str],
    user_message: str,
    quotes: list[dict[str, Any]] | None = None,
    changed_row_ids: set[str] | None = None,
) -> AgentPipelineResult:
    """Coordinator 调度 Brand / Audience / Expert（方案 A）。"""
    pipeline = AgentPipelineResult()
    row_ids = set(changed_row_ids or [])

    brand_result = None
    audience_result = None

    if "brand" in perspectives:
        brand_result = await run_brand_agent(
            project,
            user_message=user_message,
            quotes=quotes,
            changed_row_ids=row_ids,
        )
        pipeline.brand_result = brand_result
        _extend_graph(pipeline, brand_result)

    if "audience" in perspectives:
        if project.get("active_persona_id"):
            audience_result = await run_audience_agent(
                project,
                quotes=quotes,
                changed_row_ids=row_ids,
            )
            pipeline.audience_result = audience_result
            _extend_graph(pipeline, audience_result)

    run_expert = "expert" in perspectives or brand_result is not None or audience_result is not None
    if run_expert:
        expert_only = "expert" in perspectives and brand_result is None and audience_result is None
        expert_result = await run_expert_coordinator(
            project,
            brand_result=brand_result,
            audience_result=audience_result,
            user_message=user_message,
            quotes=quotes,
            changed_row_ids=row_ids,
            expert_only=expert_only,
        )
        pipeline.expert_result = expert_result
        _extend_graph(pipeline, expert_result)
        pipeline.assistant_reply = expert_result.get("assistant_reply", "")

    return pipeline


def merge_pipeline_into_project_graph(
    project: dict[str, Any],
    pipeline: AgentPipelineResult,
    *,
    replace_agent_sources: set[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    from app.models.rationale_ops import merge_proposed_graph

    user_node_ids = {n["node_id"] for n in project.get("rationale_nodes", []) if n.get("created_by") == "user"}
    safe_nodes = [n for n in pipeline.proposed_nodes if n.get("node_id") not in user_node_ids]
    updated_existing = apply_node_updates(project.get("rationale_nodes", []), pipeline.node_updates)

    nodes, edges = merge_proposed_graph(
        project_id=str(project.get("_id") or ""),
        existing_nodes=updated_existing,
        existing_edges=project.get("rationale_edges", []),
        proposed_nodes=safe_nodes,
        proposed_edges=pipeline.proposed_edges,
        replace_agent_sources=replace_agent_sources,
    )
    return nodes, edges, safe_nodes
