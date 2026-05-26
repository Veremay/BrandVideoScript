import type { ArtifactKey, ArtifactStaleness, StaleStatus } from "@/lib/types";

const ARTIFACT_LABELS: Record<ArtifactKey, string> = {
  rationale_graph: "Node graph",
  modification_schemes: "Revision schemes",
  negotiation_preparation: "Negotiation prep"
};

export function isStaleStatus(status: StaleStatus | string | undefined): boolean {
  return typeof status === "string" && status.startsWith("stale_");
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
