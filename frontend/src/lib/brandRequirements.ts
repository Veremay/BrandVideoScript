import type { BrandPerspectiveResult, BrandRequirement, BrandRequirementConfidence, Project } from "@/lib/types";

function normalizeConfidence(value: unknown): BrandRequirementConfidence {
  if (value === "high" || value === "low") return value;
  return "medium";
}

export function requirementFromRaw(raw: unknown, index: number, prefix: string): BrandRequirement | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  const text = String(record.text ?? "").trim();
  if (!text) return null;

  const id = String(record.id ?? "").trim() || `${prefix}_${index}_${Date.now()}`;
  const evidence = String(record.evidence ?? "").trim();
  const source = record.source === "user" ? "user" : record.source === "agent" ? "agent" : undefined;

  return {
    id,
    text,
    confidence: normalizeConfidence(record.confidence),
    ...(evidence ? { evidence } : {}),
    ...(source ? { source } : {})
  };
}

export function requirementsFromProject(project: Project): {
  explicit: BrandRequirement[];
  implicit: BrandRequirement[];
} {
  const result = project.brand_perspective_result;
  return requirementsFromPerspective(result);
}

export function requirementsFromPerspective(result: BrandPerspectiveResult | null | undefined): {
  explicit: BrandRequirement[];
  implicit: BrandRequirement[];
} {
  const explicitRaw = Array.isArray(result?.explicit_requirements) ? result.explicit_requirements : [];
  const implicitRaw = Array.isArray(result?.implicit_requirements) ? result.implicit_requirements : [];

  const explicit = explicitRaw
    .map((item, index) => requirementFromRaw(item, index, "explicit"))
    .filter((item): item is BrandRequirement => item !== null);
  const implicit = implicitRaw
    .map((item, index) => requirementFromRaw(item, index, "implicit"))
    .filter((item): item is BrandRequirement => item !== null);

  return { explicit, implicit };
}

export function createEmptyRequirement(prefix: string): BrandRequirement {
  return {
    id: `${prefix}_${crypto.randomUUID()}`,
    text: "",
    confidence: "medium",
    source: "user"
  };
}

export function toApiRequirements(items: BrandRequirement[]) {
  return items
    .map((item) => ({
      id: item.id,
      text: item.text.trim(),
      evidence: item.evidence?.trim() || undefined,
      confidence: item.confidence,
      ...(item.source ? { source: item.source } : {})
    }))
    .filter((item) => item.text.length > 0);
}
