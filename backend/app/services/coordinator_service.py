from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.artifact_stale import mark_persona_changed, stale_set_fields
from app.models.rationale_ops import merge_proposed_graph
from app.models.script import now_iso
from app.repositories.projects import get_project
from app.services.agents.audience_agent import run_audience_agent
from app.services.agents.brand_agent import run_brand_agent
from app.services.agents.expert_agent import run_expert_for_audience, run_expert_for_brief
from app.services.persona_analytics import PersonaAnalyticsContext, get_persona_analytics_provider


async def run_brief_initial_parse(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    brief = project.get("brief") or {}
    if not str(brief.get("text") or "").strip():
        raise ValueError("Brief text is empty")

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"brief.parse_status": "parsing", "updated_at": now_iso()}},
    )

    try:
        brand_result = await run_brand_agent(project)
        expert_result = await run_expert_for_brief(project, brand_result)

        user_nodes = [n for n in project.get("rationale_nodes", []) if n.get("created_by") == "user"]
        user_edges = [e for e in project.get("rationale_edges", []) if e.get("created_by") == "user"]
        nodes, edges = merge_proposed_graph(
            project_id=project_id,
            existing_nodes=user_nodes,
            existing_edges=user_edges,
            proposed_nodes=expert_result.get("proposed_nodes", []),
            proposed_edges=expert_result.get("proposed_edges", []),
        )

        existing_insights = [
            insight
            for insight in project.get("brand_insights", [])
            if insight.get("created_by") != "agent"
        ]
        new_insights = [*existing_insights, *brand_result.get("brand_insights", [])]

        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "brief.parse_status": "parsed",
                    "brand_perspective_result": {
                        k: v
                        for k, v in brand_result.items()
                        if k not in {"brand_insights", "proposed_nodes", "proposed_edges"}
                    },
                    "expert_perspective_result": {
                        k: v
                        for k, v in expert_result.items()
                        if k not in {"proposed_nodes", "proposed_edges"}
                    },
                    "brand_insights": new_insights,
                    "rationale_nodes": nodes,
                    "rationale_edges": edges,
                    "stale.rationale_graph": "up_to_date",
                    "stale.modification_schemes": "stale_graph_changed",
                    "updated_at": now_iso(),
                }
            },
        )
    except Exception:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"brief.parse_status": "failed", "updated_at": now_iso()}},
        )
        raise

    updated = await get_project(db, project_id, user_id)
    return {
        "project": updated,
        "parse_summary": {
            "brand_issues": len([n for n in nodes if n.get("source_type", "").startswith("brand")]),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        },
    }


async def run_persona_provisioned_parse(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")
    if not project.get("active_persona_id"):
        raise ValueError("Active persona is required")

    audience_result = await run_audience_agent(project)
    expert_result = await run_expert_for_audience(project, audience_result)

    audience_sources = {"audience_persona", "audience_simulation"}
    nodes, edges = merge_proposed_graph(
        project_id=project_id,
        existing_nodes=project.get("rationale_nodes", []),
        existing_edges=project.get("rationale_edges", []),
        proposed_nodes=expert_result.get("proposed_nodes", []),
        proposed_edges=expert_result.get("proposed_edges", []),
        replace_agent_sources=audience_sources,
    )

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "audience_perspective_result": {
                    k: v
                    for k, v in audience_result.items()
                    if k not in {"proposed_nodes", "proposed_edges"}
                },
                "rationale_nodes": nodes,
                "rationale_edges": edges,
                "stale.rationale_graph": "up_to_date",
                "updated_at": now_iso(),
            }
        },
    )

    updated = await get_project(db, project_id, user_id)
    return {
        "project": updated,
        "parse_summary": {
            "audience_issues": len([n for n in nodes if str(n.get("source_type", "")).startswith("audience")]),
            "total_nodes": len(nodes),
        },
    }


async def provision_personas_from_analytics(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    platform_context: str,
    content_category: str | None = None,
    brand_name: str | None = None,
    video_topic: str | None = None,
    run_audience_parse: bool = True,
) -> dict[str, Any]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    provider = get_persona_analytics_provider()
    ctx = PersonaAnalyticsContext(
        project_id=project_id,
        platform_context=platform_context,  # type: ignore[arg-type]
        content_category=content_category,
        brand_name=brand_name,
        video_topic=video_topic,
    )
    personas = await provider.generate_personas(ctx)
    active_id = personas[0]["persona_id"] if personas else None

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "platform_context": platform_context,
                "personas": personas,
                "active_persona_id": active_id,
                "updated_at": now_iso(),
                **stale_set_fields(mark_persona_changed()),
            }
        },
    )

    parse_result: dict[str, Any] | None = None
    if run_audience_parse and active_id:
        parse_result = await run_persona_provisioned_parse(db, project_id, user_id)

    project_doc = await get_project(db, project_id, user_id)
    return {
        "personas": personas,
        "active_persona_id": active_id,
        "analytics_meta": personas[0].get("analytics_meta") if personas else None,
        "project": project_doc,
        "audience_parse": parse_result,
    }
