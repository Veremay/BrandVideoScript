import type { ArtifactKey, ArtifactStaleness, StaleStatus } from "@/lib/types";

const ARTIFACT_LABELS: Record<ArtifactKey, string> = {
  rationale_graph: "Node graph",
  modification_schemes: "Revision schemes",
  negotiation_preparation: "Negotiation prep"
};

export function isStaleStatus(status: StaleStatus | string | undefined): boolean {
  return typeof status === "string" && status.startsWith("stale_");
}

const MAP_UPDATE_STALE_STATUSES = new Set<StaleStatus>([
  "stale_script_changed",
  "stale_brief_changed",
  "stale_persona_changed"
]);

/** Node graph is out of date because the script was edited since last sync. */
export function isGraphStaleFromScript(stale: ArtifactStaleness | Record<string, string> | undefined): boolean {
  return stale?.rationale_graph === "stale_script_changed";
}

/** Node graph is out of date because script, requirements, or persona changed since last sync. */
export function isGraphStaleForUpdateMap(stale: ArtifactStaleness | Record<string, string> | undefined): boolean {
  const status = stale?.rationale_graph;
  return typeof status === "string" && MAP_UPDATE_STALE_STATUSES.has(status as StaleStatus);
}

export function staleArtifactKeys(stale: ArtifactStaleness | Record<string, string> | undefined): ArtifactKey[] {
  if (!stale) return [];
  return (Object.keys(ARTIFACT_LABELS) as ArtifactKey[]).filter((key) => isStaleStatus(stale[key]));
}

export function staleSummary(stale: ArtifactStaleness | Record<string, string> | undefined): string | null {
  const keys = staleArtifactKeys(stale);
  if (!keys.length) return null;
  return keys.map((key) => ARTIFACT_LABELS[key]).join(", ");
}
