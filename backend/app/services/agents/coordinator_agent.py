"""Coordinator Agent — orchestration-level conflict analysis.

Distinct from the Expert Agent: the Coordinator does NOT take a Brand/Audience
perspective. It reads all positions from both sides and identifies which pairs
are genuinely incompatible, then assigns conflict_tags accordingly.
"""

from __future__ import annotations

from typing import Any

from app.services.agent_llm import invoke_agent_json
from app.services.pipeline_log import log_step


async def run_conflict_tagging(
    project: dict[str, Any],
    brand_result: dict[str, Any],
    audience_result: dict[str, Any] | None,
    new_positions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Coordinator conflict analysis: assign conflict_tags to conflicting positions.

    Compares positions from Brand and Audience agents (and any existing user
    positions in the project) to identify genuine incompatibilities. Conflicting
    positions are grouped under a shared tag letter (A, B, C, …).

    Returns:
    - ``position_tag_map``:       {node_id: [tag, …]} for newly proposed positions
    - ``existing_node_updates``:  [{node_id, conflict_tags}] for existing positions
    - ``conflict_groups``:        raw groups from the LLM
    """
    project_id = str(project.get("_id") or "")

    new_pos_ids = {str(n.get("node_id", "")) for n in new_positions}

    existing_positions = [
        n for n in (project.get("rationale_nodes") or [])
        if n.get("node_type") == "position" and str(n.get("node_id", "")) not in new_pos_ids
    ]

    def _pos_summary(nodes: list[dict[str, Any]], label: str) -> str:
        if not nodes:
            return f"（{label}：无）"
        lines = [
            f"- node_id={n.get('node_id')} | source={n.get('source_type')} | "
            f"{n.get('title', '')} — {str(n.get('content', ''))[:120]}"
            for n in nodes
        ]
        return f"{label}：\n" + "\n".join(lines)

    brand_positions = [
        n for n in new_positions
        if n.get("source_type") in {"brand_brief", "brand_inferred"}
    ]
    audience_positions = [
        n for n in new_positions
        if n.get("source_type") in {"audience_persona", "audience_simulation"}
    ]
    expert_positions = [
        n for n in new_positions
        if n.get("source_type") == "expert_strategy"
    ]
    other_positions = [
        n for n in new_positions
        if n not in brand_positions and n not in audience_positions and n not in expert_positions
    ]

    context_block = "\n\n".join([
        "## 任务\nconflict_tagging — 识别冲突并为 position 分配 conflict_tag",
        _pos_summary(brand_positions, "品牌方新增 position"),
        _pos_summary(audience_positions, "观众方新增 position"),
        _pos_summary(expert_positions, "专家方新增 position"),
        _pos_summary(other_positions, "其他新增 position"),
        _pos_summary(existing_positions, "图中已有 position（含用户手动创建）"),
    ])

    log_step(
        "coordinator_agent.conflict_tagging",
        phase="IN",
        project_id=project_id,
        new_positions=len(new_positions),
        existing_positions=len(existing_positions),
    )

    def mock() -> dict[str, Any]:
        groups: list[dict[str, Any]] = []
        if brand_positions and audience_positions:
            groups.append({
                "tag": "A",
                "reason": "品牌露出诉求与观众自然性体验存在冲突",
                "position_ids": [
                    str(brand_positions[0].get("node_id", "")),
                    str(audience_positions[0].get("node_id", "")),
                ],
            })
        return {"conflict_groups": groups}

    payload = await invoke_agent_json(
        agent_prompt_file="coordinator_agent.md",
        context=context_block,
        task_type="coordinator_conflict_tagging",
        mock_payload=mock,
    )

    conflict_groups: list[dict[str, Any]] = payload.get("conflict_groups") or []

    position_tag_map: dict[str, list[str]] = {}
    existing_position_tag_map: dict[str, list[str]] = {}

    for group in conflict_groups:
        tag = str(group.get("tag") or "")
        if not tag:
            continue
        for pos_id in group.get("position_ids") or []:
            pos_id = str(pos_id)
            if pos_id in new_pos_ids:
                position_tag_map.setdefault(pos_id, [])
                if tag not in position_tag_map[pos_id]:
                    position_tag_map[pos_id].append(tag)
            else:
                existing_position_tag_map.setdefault(pos_id, [])
                if tag not in existing_position_tag_map[pos_id]:
                    existing_position_tag_map[pos_id].append(tag)

    existing_node_updates = [
        {"node_id": node_id, "conflict_tags": tags}
        for node_id, tags in existing_position_tag_map.items()
    ]

    log_step(
        "coordinator_agent.conflict_tagging",
        phase="OUT",
        project_id=project_id,
        conflict_groups=len(conflict_groups),
        tagged_new=len(position_tag_map),
        tagged_existing=len(existing_position_tag_map),
    )
    return {
        "position_tag_map": position_tag_map,
        "existing_node_updates": existing_node_updates,
        "conflict_groups": conflict_groups,
        "proposed_nodes": [],
        "proposed_edges": [],
        "node_updates": [],
    }
