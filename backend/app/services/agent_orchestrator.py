from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.services.agents.audience_agent import run_audience_agent
from app.services.agents.brand_agent import run_brand_agent
from app.services.agents.expert_agent import (
    run_expert_coordinator,
    run_expert_for_audience,
    run_expert_for_map_update,
    run_expert_reconcile,
)
from app.services.agents.coordinator_agent import run_conflict_tagging

__all__ = [
    "AgentPipelineResult",
    "merge_pipeline_into_project_graph",
    "reconcile_pipeline_into_project_graph",
    "run_audience_pipeline",
    "run_brief_initial_pipeline",
    "run_coordinator_pipeline",
    "run_issue_population_pipeline",
    "run_map_update_pipeline",
    "run_reconcile_pipeline",
]
from app.services.pipeline_log import log_step
from app.services.tools.ibis_graph import apply_node_updates
from app.models.rationale_ops import build_rationale_edge, build_rationale_node

MAP_UPDATE_REPLACE_SOURCES = {
    "brand_brief",
    "brand_inferred",
    "audience_persona",
    "audience_simulation",
    "expert_strategy",
}


@dataclass
class AgentPipelineResult:
    proposed_nodes: list[dict[str, Any]] = field(default_factory=list)
    proposed_edges: list[dict[str, Any]] = field(default_factory=list)
    node_updates: list[dict[str, Any]] = field(default_factory=list)
    # Reconcile (anchored re-evaluation) outputs.
    issue_reviews: list[dict[str, Any]] = field(default_factory=list)
    node_modifications: list[dict[str, Any]] = field(default_factory=list)
    # Conflict tagging: [{node_id, conflict_tags}] for existing positions; applied post-merge.
    conflict_tag_updates: list[dict[str, Any]] = field(default_factory=list)
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


def _normalize_issue_key(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _existing_issue_position_sets(project: dict[str, Any]) -> dict[frozenset[str], str]:
    issue_ids = {
        str(n.get("node_id"))
        for n in project.get("rationale_nodes", [])
        if n.get("node_type") == "issue" and n.get("lifecycle", "active") == "active"
    }
    result: dict[frozenset[str], str] = {}
    for issue_id in issue_ids:
        position_ids = frozenset(
            str(edge.get("from_node_id"))
            for edge in project.get("rationale_edges", [])
            if edge.get("relation_type") == "responds_to" and str(edge.get("to_node_id")) == issue_id
        )
        if position_ids:
            result[position_ids] = issue_id
    return result


BRAND_SOURCE_TYPES = {"brand_brief", "brand_inferred"}
AUDIENCE_SOURCE_TYPES = {"audience_persona", "audience_simulation"}


def _position_source_family(node: dict[str, Any]) -> str:
    source_type = str(node.get("source_type") or "")
    perspective = str(node.get("source_perspective") or "")
    if source_type in BRAND_SOURCE_TYPES:
        return "brand"
    if source_type in AUDIENCE_SOURCE_TYPES:
        return "audience"
    if source_type == "expert_strategy":
        return "expert"
    if perspective in {"brand", "audience", "expert"}:
        return perspective
    return "other"


def _text_mentions_brand_and_audience(text: str) -> bool:
    lowered = text.lower()
    brand_terms = ("brand", "品牌")
    audience_terms = ("audience", "viewer", "观众", "用户")
    return any(term in lowered for term in brand_terms) and any(term in lowered for term in audience_terms)


def _expand_expert_only_position_ids(
    pipeline: AgentPipelineResult,
    position_ids: list[str],
    *,
    title: str,
    content: str,
) -> list[str]:
    """If an Expert issue summarizes Brand/Audience trade-offs, show those positions too."""
    if not position_ids or not _text_mentions_brand_and_audience(f"{title}\n{content}"):
        return position_ids

    positions_by_id = {
        str(n.get("node_id")): n
        for n in pipeline.proposed_nodes
        if n.get("node_type") == "position" and n.get("node_id")
    }
    families = {_position_source_family(positions_by_id[pos_id]) for pos_id in position_ids if pos_id in positions_by_id}
    if "expert" not in families:
        return position_ids

    expanded = list(position_ids)
    missing_families = {"brand", "audience"} - families
    for node in pipeline.proposed_nodes:
        node_id = str(node.get("node_id") or "")
        if node.get("node_type") != "position" or not node_id or node_id in expanded:
            continue
        if _position_source_family(node) in missing_families:
            expanded.append(node_id)
            missing_families.discard(_position_source_family(node))
        if not missing_families:
            break
    return expanded


def _append_decision_issues(
    project: dict[str, Any],
    pipeline: AgentPipelineResult,
    decision_issues: list[dict[str, Any]],
) -> None:
    """Materialize Coordinator-suggested decision axes as Issue nodes.

    Conflict remains expressed by Position ``conflict_tags``. These Issues are
    topic containers only: they group Positions that answer the same durable
    decision question.
    """
    if not decision_issues:
        return

    project_id = str(project.get("_id") or "")
    valid_position_ids = {
        str(n.get("node_id"))
        for n in [*project.get("rationale_nodes", []), *pipeline.proposed_nodes]
        if n.get("node_type") == "position" and n.get("node_id")
    }
    existing_issue_titles = {
        _normalize_issue_key(str(n.get("title") or ""))
        for n in project.get("rationale_nodes", [])
        if n.get("node_type") == "issue" and n.get("lifecycle", "active") == "active"
    }
    existing_position_sets = _existing_issue_position_sets(project)
    seen_edges = {
        (str(e.get("from_node_id")), str(e.get("to_node_id")), str(e.get("relation_type")))
        for e in [*project.get("rationale_edges", []), *pipeline.proposed_edges]
    }

    for spec in decision_issues:
        if not isinstance(spec, dict):
            continue
        title = str(spec.get("title") or "").strip()
        content = str(spec.get("content") or spec.get("reason") or "").strip()
        if not title:
            continue
        position_ids: list[str] = []
        for raw_id in spec.get("position_ids") or []:
            position_id = str(raw_id)
            if position_id in valid_position_ids and position_id not in position_ids:
                position_ids.append(position_id)
        position_ids = _expand_expert_only_position_ids(
            pipeline,
            position_ids,
            title=title,
            content=content,
        )
        if not position_ids:
            continue
        position_set = frozenset(position_ids)
        if _normalize_issue_key(title) in existing_issue_titles:
            continue
        if position_set in existing_position_sets:
            continue

        issue = build_rationale_node(
            project_id=project_id,
            node_type="issue",
            title=title,
            content=content,
            source_type="expert_strategy",
            source_perspective="expert",
            created_by="agent",
        )
        pipeline.proposed_nodes.append(issue)
        existing_issue_titles.add(_normalize_issue_key(title))
        existing_position_sets[position_set] = str(issue["node_id"])
        for position_id in position_ids:
            key = (position_id, str(issue["node_id"]), "responds_to")
            if key in seen_edges:
                continue
            seen_edges.add(key)
            pipeline.proposed_edges.append(
                build_rationale_edge(
                    project_id=project_id,
                    from_node_id=position_id,
                    to_node_id=str(issue["node_id"]),
                    relation_type="responds_to",
                    created_by="agent",
                )
            )


def _append_carrier_issues_for_orphan_positions(project: dict[str, Any], pipeline: AgentPipelineResult) -> None:
    """Ensure every proposed Position has an Issue container."""
    project_id = str(project.get("_id") or "")
    existing_position_ids_with_issue = {
        str(edge.get("from_node_id"))
        for edge in project.get("rationale_edges", [])
        if edge.get("relation_type") == "responds_to" and edge.get("from_node_id")
    }
    proposed_position_ids_with_issue = {
        str(edge.get("from_node_id"))
        for edge in pipeline.proposed_edges
        if edge.get("relation_type") == "responds_to" and edge.get("from_node_id")
    }
    for position in list(pipeline.proposed_nodes):
        if position.get("node_type") != "position" or not position.get("node_id"):
            continue
        position_id = str(position["node_id"])
        if position_id in existing_position_ids_with_issue or position_id in proposed_position_ids_with_issue:
            continue
        title = str(position.get("title") or "").strip()
        if not title:
            continue
        issue_title = _carrier_issue_title_for_position(position)
        issue = build_rationale_node(
            project_id=project_id,
            node_type="issue",
            title=issue_title,
            content=f"承载立场：{title}",
            source_type=str(position.get("source_type") or "expert_strategy"),
            source_perspective=str(position.get("source_perspective") or "expert"),
            created_by=str(position.get("created_by") or "agent"),
        )
        pipeline.proposed_nodes.append(issue)
        pipeline.proposed_edges.append(
            build_rationale_edge(
                project_id=project_id,
                from_node_id=position_id,
                to_node_id=str(issue["node_id"]),
                relation_type="responds_to",
                created_by=str(position.get("created_by") or "agent"),
            )
        )
        proposed_position_ids_with_issue.add(position_id)


def _carrier_issue_title_for_position(position: dict[str, Any]) -> str:
    """Create a decision-axis title instead of echoing a single Position."""
    source_type = str(position.get("source_type") or "")
    perspective = str(position.get("source_perspective") or "")
    if source_type.startswith("brand_") or perspective == "brand":
        return "How should brand visibility be balanced against audience acceptance?"
    if source_type.startswith("audience_") or perspective == "audience":
        return "How should audience attention be protected while meeting project goals?"
    if source_type == "expert_strategy" or perspective == "expert":
        return "Which creative trade-off should guide this script revision?"
    title = str(position.get("title") or "").strip()
    if title:
        return f"What decision does this position require: {title[:60]}?"
    return "What decision should this position inform?"


async def run_brief_initial_pipeline(project: dict[str, Any]) -> AgentPipelineResult:
    """Brief 解析：只提取品牌需求，不生成 IBIS 节点。

    节点生成由用户点击 Update Map 后的 run_map_update_pipeline 触发。
    """
    project_id = str(project.get("_id") or "")
    log_step("pipeline.brief_initial", phase="IN", project_id=project_id)

    pipeline = AgentPipelineResult()
    log_step("pipeline.brief_initial.brand_agent", phase="IN", project_id=project_id)
    brand_result = await run_brand_agent(project, task_context="brief_parse")
    _log_agent_output("pipeline.brief_initial.brand_agent", brand_result)
    pipeline.brand_result = brand_result

    log_step(
        "pipeline.brief_initial",
        phase="OUT",
        project_id=project_id,
        requirements=len(brand_result.get("brand_insights") or []),
    )
    return pipeline


async def run_map_update_pipeline(
    project: dict[str, Any],
    *,
    changed_row_ids: set[str] | None = None,
    progress_queue: asyncio.Queue | None = None,
) -> AgentPipelineResult:
    """Update Map: Brand + Audience + Expert generate positions; Coordinator assigns conflict_tags.

    No Issue nodes are created in this pipeline — conflicts are expressed as
    ``conflict_tags`` (e.g. ["A"]) on the position nodes themselves.
    """
    project_id = str(project.get("_id") or "")
    row_ids = set(changed_row_ids or [])
    log_step("pipeline.map_update", phase="IN", project_id=project_id, changed_row_ids=sorted(row_ids))

    async def _push_progress(message: str) -> None:
        if progress_queue is not None:
            await progress_queue.put({"message": message})

    pipeline = AgentPipelineResult()
    map_message = (
        "请基于变动脚本行重新分析品牌立场。"
        if row_ids
        else "请基于当前完整脚本重新分析品牌立场。"
    )

    await _push_progress("Analyzing brand perspective…")
    log_step("pipeline.map_update.brand_agent", phase="IN", project_id=project_id)
    brand_result = await run_brand_agent(
        project,
        task_context="coordinator",
        user_message=map_message,
        changed_row_ids=row_ids,
        full_script=not row_ids,
    )
    _log_agent_output("pipeline.map_update.brand_agent", brand_result)
    pipeline.brand_result = brand_result
    _extend_graph(pipeline, brand_result)

    audience_result = None
    if project.get("active_persona_id"):
        await _push_progress("Analyzing audience perspective…")
        log_step("pipeline.map_update.audience_agent", phase="IN", project_id=project_id)
        audience_result = await run_audience_agent(
            project,
            changed_row_ids=row_ids,
            full_script=not row_ids,
        )
        _log_agent_output("pipeline.map_update.audience_agent", audience_result)
        pipeline.audience_result = audience_result
        _extend_graph(pipeline, audience_result)

    await _push_progress("Expert strategy analysis…")
    log_step("pipeline.map_update.expert_agent", phase="IN", project_id=project_id)
    expert_result = await run_expert_for_map_update(
        project,
        brand_result=brand_result,
        audience_result=audience_result,
        changed_row_ids=row_ids,
        full_script=not row_ids,
    )
    _log_agent_output("pipeline.map_update.expert_agent", expert_result)
    pipeline.expert_result = expert_result
    _extend_graph(pipeline, expert_result)

    # Coordinator conflict tagging: assign conflict_tags to positions; no Issue nodes created.
    new_positions = [n for n in pipeline.proposed_nodes if n.get("node_type") == "position"]
    if new_positions:
        await _push_progress("Resolving conflicts…")
        log_step("pipeline.map_update.conflict_tagging", phase="IN", project_id=project_id)
        tag_result = await run_conflict_tagging(project, brand_result, audience_result, new_positions)

        # Apply conflict_tags directly to the proposed position nodes (pre-merge)
        tag_map: dict[str, list[str]] = tag_result.get("position_tag_map") or {}
        for node in pipeline.proposed_nodes:
            node_id = str(node.get("node_id", ""))
            if node_id in tag_map:
                node["conflict_tags"] = tag_map[node_id]

        # Store existing-position tag updates on the pipeline for graph_sync to apply post-merge
        pipeline.conflict_tag_updates = tag_result.get("existing_node_updates") or []
        _append_decision_issues(project, pipeline, tag_result.get("decision_issues") or [])

        log_step(
            "pipeline.map_update.conflict_tagging",
            phase="OUT",
            project_id=project_id,
            tagged_new=len(tag_map),
            existing_updates=len(pipeline.conflict_tag_updates),
            decision_issues=len(tag_result.get("decision_issues") or []),
        )
    _append_carrier_issues_for_orphan_positions(project, pipeline)

    log_step(
        "pipeline.map_update",
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
            task_context="coordinator",
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
    """Brand + Audience generate one position each for a user-created issue (scoped update)."""
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
    if issue.get("created_by") != "user":
        raise ValueError("Only user-created issues support Generate Position")

    log_step("pipeline.populate_issue", phase="IN", project_id=project_id, issue_id=issue_id)
    pipeline = AgentPipelineResult()

    log_step("pipeline.populate_issue.brand_agent", phase="IN", project_id=project_id, issue_id=issue_id)
    brand_result = await run_brand_agent(project, task_context="issue_response", issue=issue)
    _log_agent_output("pipeline.populate_issue.brand_agent", brand_result)
    pipeline.brand_result = brand_result
    _extend_graph(pipeline, brand_result)

    if project.get("active_persona_id"):
        log_step("pipeline.populate_issue.audience_agent", phase="IN", project_id=project_id, issue_id=issue_id)
        audience_result = await run_audience_agent(project, task_context="issue_response", issue=issue)
        _log_agent_output("pipeline.populate_issue.audience_agent", audience_result)
        pipeline.audience_result = audience_result
        _extend_graph(pipeline, audience_result)

    pipeline.assistant_reply = (
        f"已为议题「{issue.get('title', '')[:40]}」生成品牌与观众的立场及论据。"
    )

    log_step(
        "pipeline.populate_issue",
        phase="OUT",
        project_id=project_id,
        total_nodes=len(pipeline.proposed_nodes),
        total_edges=len(pipeline.proposed_edges),
    )
    return pipeline


async def run_reconcile_pipeline(
    project: dict[str, Any],
    *,
    user_message: str = "",
    changed_row_ids: set[str] | None = None,
) -> AgentPipelineResult:
    """Anchored reconcile for "update map": Expert re-evaluates existing Issues."""
    project_id = str(project.get("_id") or "")
    log_step("pipeline.reconcile", phase="IN", project_id=project_id)

    pipeline = AgentPipelineResult()
    expert_result = await run_expert_reconcile(
        project,
        changed_row_ids=changed_row_ids,
        user_message=user_message,
    )
    _log_agent_output("pipeline.reconcile.expert", expert_result)
    pipeline.expert_result = expert_result
    _extend_graph(pipeline, expert_result)
    pipeline.issue_reviews = expert_result.get("issue_reviews") or []
    pipeline.node_modifications = expert_result.get("node_modifications") or []
    pipeline.assistant_reply = expert_result.get("assistant_reply", "")
    _append_carrier_issues_for_orphan_positions(project, pipeline)

    log_step(
        "pipeline.reconcile",
        phase="OUT",
        project_id=project_id,
        issue_reviews=len(pipeline.issue_reviews),
        node_modifications=len(pipeline.node_modifications),
        new_nodes=len(pipeline.proposed_nodes),
    )
    return pipeline


def reconcile_pipeline_into_project_graph(
    project: dict[str, Any],
    pipeline: AgentPipelineResult,
) -> tuple[list[dict], list[dict]]:
    """Apply a reconcile pipeline result to the project's live graph."""
    from app.models.rationale_ops import apply_reconcile

    return apply_reconcile(
        project_id=str(project.get("_id") or ""),
        existing_nodes=project.get("rationale_nodes", []),
        existing_edges=project.get("rationale_edges", []),
        issue_reviews=pipeline.issue_reviews,
        node_modifications=pipeline.node_modifications,
        new_nodes=pipeline.proposed_nodes,
        new_edges=pipeline.proposed_edges,
    )


def merge_pipeline_into_project_graph(
    project: dict[str, Any],
    pipeline: AgentPipelineResult,
    *,
    replace_agent_sources: set[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    from app.models.rationale_ops import merge_proposed_graph

    _append_carrier_issues_for_orphan_positions(project, pipeline)
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


def discard_non_conflicting_pipeline_positions(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    pipeline: AgentPipelineResult,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Drop pipeline-added positions that are not linked to an issue via responds_to."""
    pipeline_position_ids = {
        str(n["node_id"])
        for n in pipeline.proposed_nodes
        if n.get("node_type") == "position"
    }
    if not pipeline_position_ids:
        return nodes, edges

    issue_ids = {str(n["node_id"]) for n in nodes if n.get("node_type") == "issue" and n.get("node_id")}
    connected_positions = {
        str(edge["from_node_id"])
        for edge in edges
        if edge.get("relation_type") == "responds_to"
        and str(edge.get("to_node_id") or "") in issue_ids
        and str(edge.get("from_node_id") or "") in pipeline_position_ids
    }
    remove_ids = pipeline_position_ids - connected_positions
    if not remove_ids:
        return nodes, edges

    kept_nodes = [n for n in nodes if str(n.get("node_id") or "") not in remove_ids]
    kept_edges = [
        e
        for e in edges
        if str(e.get("from_node_id") or "") not in remove_ids
        and str(e.get("to_node_id") or "") not in remove_ids
    ]
    return kept_nodes, kept_edges
