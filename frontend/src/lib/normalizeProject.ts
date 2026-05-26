import type { Project, RationaleEdge, RationaleNode } from "@/lib/types";

type ProjectPayload = Project & { id?: string };

export function normalizeProject(raw: ProjectPayload | null): Project | null {
  if (!raw) return null;

  const projectId = raw._id || raw.id || "";
  return {
    ...raw,
    _id: projectId,
    rationale_nodes: (raw.rationale_nodes ?? []) as RationaleNode[],
    rationale_edges: (raw.rationale_edges ?? []) as RationaleEdge[],
    negotiation_queue: raw.negotiation_queue ?? [],
    brand_perspective_result: raw.brand_perspective_result ?? null,
    audience_perspective_result: raw.audience_perspective_result ?? null,
    expert_perspective_result: raw.expert_perspective_result ?? null,
    platform_context: raw.platform_context ?? "other"
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
    rationale_edges: previous.rationale_edges ?? []
  };
}
