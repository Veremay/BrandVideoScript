from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.agents.audience_agent import run_audience_agent
from app.services.agents.brand_agent import run_brand_agent
from app.services.agents.expert_agent import (
    run_expert_coordinator,
    run_expert_for_audience,
    run_expert_for_brief,
    run_expert_populate_issue,
)
from app.services.pipeline_log import log_step
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


def _log_agent_output(step: str, output: dict[str, Any]) -> None:
    log_step(
        step,
        phase="OUT",
        proposed_nodes=len(output.get("proposed_nodes") or []),
        proposed_edges=len(output.get("proposed_edges") or []),
        node_updates=len(output.get("node_updates") or []),
        assistant_reply=(output.get("assistant_reply") or "")[:500],
        summary={k: v for k, v in output.items() if k not in {"proposed_nodes", "proposed_edges", "node_updates"}},
    )


async def run_brief_initial_pipeline(project: dict[str, Any]) -> AgentPipelineResult:
    """Brand Agent → Expert Agent；图节点经 persist_rationale_graph 工具落库。"""
    project_id = str(project.get("_id") or "")
    log_step("pipeline.brief_initial", phase="IN", project_id=project_id)

    pipeline = AgentPipelineResult()
    log_step("pipeline.brief_initial.brand_agent", phase="IN", project_id=project_id)
    brand_result = await run_brand_agent(project)
    _log_agent_output("pipeline.brief_initial.brand_agent", brand_result)
    pipeline.brand_result = brand_result
    _extend_graph(pipeline, brand_result)

    log_step("pipeline.brief_initial.expert_for_brief", phase="IN", project_id=project_id)
    expert_result = await run_expert_for_brief(project, brand_result)
    _log_agent_output("pipeline.brief_initial.expert_for_brief", expert_result)
    pipeline.expert_result = expert_result
    _extend_graph(pipeline, expert_result)

    log_step(
        "pipeline.brief_initial",
        phase="OUT",
        project_id=project_id,
        total_nodes=len(pipeline.proposed_nodes),
        total_edges=len(pipeline.proposed_edges),
    )
    return pipeline


async def run_audience_pipeline(project: dict[str, Any]) -> AgentPipelineResult:
    """Audience Agent → Expert Agent。"""
    project_id = str(project.get("_id") or "")
    log_step("pipeline.audience", phase="IN", project_id=project_id)

    pipeline = AgentPipelineResult()
    log_step("pipeline.audience.audience_agent", phase="IN", project_id=project_id)
    audience_result = await run_audience_agent(project)
    _log_agent_output("pipeline.audience.audience_agent", audience_result)
    pipeline.audience_result = audience_result
    _extend_graph(pipeline, audience_result)

    log_step("pipeline.audience.expert_for_audience", phase="IN", project_id=project_id)
    expert_result = await run_expert_for_audience(project, audience_result)
    _log_agent_output("pipeline.audience.expert_for_audience", expert_result)
    pipeline.expert_result = expert_result
    _extend_graph(pipeline, expert_result)

    log_step(
        "pipeline.audience",
        phase="OUT",
        project_id=project_id,
        total_nodes=len(pipeline.proposed_nodes),
        total_edges=len(pipeline.proposed_edges),
    )
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
    project_id = str(project.get("_id") or "")
    log_step(
        "pipeline.coordinator",
        phase="IN",
        project_id=project_id,
        perspectives=sorted(perspectives),
        user_message=user_message,
        quotes=quotes,
        changed_row_ids=sorted(changed_row_ids or []),
    )

    pipeline = AgentPipelineResult()
    row_ids = set(changed_row_ids or [])

    brand_result = None
    audience_result = None

    if "brand" in perspectives:
        log_step("pipeline.coordinator.brand_agent", phase="IN", project_id=project_id)
        brand_result = await run_brand_agent(
            project,
            user_message=user_message,
            quotes=quotes,
            changed_row_ids=row_ids,
        )
        _log_agent_output("pipeline.coordinator.brand_agent", brand_result)
        pipeline.brand_result = brand_result
        _extend_graph(pipeline, brand_result)

    if "audience" in perspectives:
        if project.get("active_persona_id"):
            log_step("pipeline.coordinator.audience_agent", phase="IN", project_id=project_id)
            audience_result = await run_audience_agent(
                project,
                quotes=quotes,
                changed_row_ids=row_ids,
            )
            _log_agent_output("pipeline.coordinator.audience_agent", audience_result)
            pipeline.audience_result = audience_result
            _extend_graph(pipeline, audience_result)

    run_expert = "expert" in perspectives or brand_result is not None or audience_result is not None
    if run_expert:
        expert_only = "expert" in perspectives and brand_result is None and audience_result is None
        log_step(
            "pipeline.coordinator.expert",
            phase="IN",
            project_id=project_id,
            expert_only=expert_only,
        )
        expert_result = await run_expert_coordinator(
            project,
            brand_result=brand_result,
            audience_result=audience_result,
            user_message=user_message,
            quotes=quotes,
            changed_row_ids=row_ids,
            expert_only=expert_only,
        )
        _log_agent_output("pipeline.coordinator.expert", expert_result)
        pipeline.expert_result = expert_result
        _extend_graph(pipeline, expert_result)
        pipeline.assistant_reply = expert_result.get("assistant_reply", "")

    log_step(
        "pipeline.coordinator",
        phase="OUT",
        project_id=project_id,
        total_nodes=len(pipeline.proposed_nodes),
        total_edges=len(pipeline.proposed_edges),
        assistant_reply=pipeline.assistant_reply[:500],
    )
    return pipeline


async def run_issue_population_pipeline(
    project: dict[str, Any],
    issue_id: str,
) -> AgentPipelineResult:
    """Expert organizes ≥2 conflicting Positions around a user-created Issue."""
    project_id = str(project.get("_id") or "")
    issue = next(
        (
            n
            for n in project.get("rationale_nodes", [])
            if n.get("node_id") == issue_id and n.get("node_type") == "issue"
        ),
        None,
    )
    if issue is None:
        raise ValueError("Issue node not found")

    log_step("pipeline.populate_issue", phase="IN", project_id=project_id, issue_id=issue_id)
    pipeline = AgentPipelineResult()
    expert_result = await run_expert_populate_issue(project, issue)
    _log_agent_output("pipeline.populate_issue.expert", expert_result)
    pipeline.expert_result = expert_result
    _extend_graph(pipeline, expert_result)
    pipeline.assistant_reply = expert_result.get("assistant_reply", "")

    log_step(
        "pipeline.populate_issue",
        phase="OUT",
        project_id=project_id,
        total_nodes=len(pipeline.proposed_nodes),
        total_edges=len(pipeline.proposed_edges),
    )
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
