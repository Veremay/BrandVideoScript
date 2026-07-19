import type { Project, RationaleEdge, RationaleNode, Script } from "@/lib/types";

type ProjectPayload = Project & { id?: string };

function clearLegacyDurationRanges(script: Script): Script {
  const durationColumnIds = new Set(
    script.columns.filter((column) => column.type === "duration").map((column) => column.column_id)
  );
  let changed = false;
  const rows = script.rows.map((row) => ({
    ...row,
    cells: row.cells.map((cell) => {
      const isLegacyRange = /^\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*$/.test(cell.value);
      if (!durationColumnIds.has(cell.column_id) || !isLegacyRange) return cell;
      changed = true;
      return { ...cell, value: "" };
    })
  }));
  return changed ? { ...script, rows } : script;
}

export function normalizeProject(raw: ProjectPayload | null): Project | null {
  if (!raw) return null;

  const projectId = raw._id || raw.id || "";
  const currentScript = clearLegacyDurationRanges(raw.current_script);
  return {
    ...raw,
    _id: projectId,
    current_script: currentScript,
    rationale_nodes: (raw.rationale_nodes ?? []) as RationaleNode[],
    rationale_edges: (raw.rationale_edges ?? []) as RationaleEdge[],
    consideration_queue: raw.consideration_queue ?? raw.negotiation_queue ?? [],
    communication_support_queue: raw.communication_support_queue ?? [],
    choice_history: raw.choice_history ?? { adopted_positions: [], scheme_position_links: [] },
    negotiation_preparation: raw.negotiation_preparation ?? null,
    modification_schemes: (raw.modification_schemes ?? []).slice(-1),
    brand_perspective_result: raw.brand_perspective_result ?? null,
    audience_perspective_result: raw.audience_perspective_result ?? null,
    expert_perspective_result: raw.expert_perspective_result ?? null,
    platform_context: raw.platform_context ?? "other",
    video_category: raw.video_category ?? "lifestyle",
    mode: raw.mode ?? currentScript.settings?.mode ?? "full"
  };
}

export function mergeProjectPreservingGraph(previous: Project | null, incoming: Project): Project {
  const normalized = normalizeProject(incoming);
  if (!normalized || !previous) return normalized ?? incoming;

  const hasIncomingGraph =
    (normalized.rationale_nodes?.length ?? 0) > 0 || (normalized.rationale_edges?.length ?? 0) > 0;
  if (hasIncomingGraph) return normalized;

  return {
    ...normalized,
    rationale_nodes: previous.rationale_nodes ?? [],
    rationale_edges: previous.rationale_edges ?? [],
    modification_schemes:
      (normalized.modification_schemes?.length ?? 0) > 0
        ? normalized.modification_schemes
        : (previous.modification_schemes ?? [])
  };
}
