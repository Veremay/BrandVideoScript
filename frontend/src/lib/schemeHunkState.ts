import type { HunkDecision, ModificationScheme, ModificationSchemeHunk, Script } from "@/lib/types";

export type HunkDecisionState = "pending" | "accepted" | "rejected";

export function scriptCellValue(script: Script, rowId: string, columnId: string): string {
  const row = script.rows.find((item) => item.row_id === rowId);
  return row?.cells.find((cell) => cell.column_id === columnId)?.value ?? "";
}

export function isHunkAppliedInScript(script: Script, hunk: ModificationSchemeHunk): boolean {
  return scriptCellValue(script, hunk.row_id, hunk.column_id) === hunk.added;
}

export function deriveHunkDecision(
  script: Script,
  hunk: ModificationSchemeHunk & { decision?: HunkDecisionState }
): HunkDecision {
  if (hunk.decision === "accepted") return true;
  if (hunk.decision === "rejected") return false;
  if (isHunkAppliedInScript(script, hunk)) return true;
  return null;
}

export function deriveHunkDecisions(script: Script, scheme: ModificationScheme): Record<string, HunkDecision> {
  const decisions: Record<string, HunkDecision> = {};
  for (const hunk of scheme.hunks) {
    decisions[hunk.hunk_id] = deriveHunkDecision(script, hunk);
  }
  return decisions;
}

export function findScheme(project: { modification_schemes?: ModificationScheme[] }, schemeId?: string) {
  const schemes = project.modification_schemes ?? [];
  if (!schemes.length) return null;
  if (schemeId) {
    return schemes.find((scheme) => scheme.scheme_id === schemeId) ?? schemes[schemes.length - 1];
  }
  return schemes[schemes.length - 1];
}
