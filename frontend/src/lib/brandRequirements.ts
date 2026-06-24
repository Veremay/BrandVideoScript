import type {
  BrandInsight,
  BrandInsightCategory,
  BrandInsightConfidence,
  Project
} from "@/lib/types";

function normalizeConfidence(value: unknown): BrandInsightConfidence {
  if (value === "high" || value === "low") return value;
  return "medium";
}

function normalizeCategory(value: unknown, fallback: BrandInsightCategory): BrandInsightCategory {
  if (value === "explicit_requirement" || value === "implicit_requirement") return value;
  return fallback;
}

export function insightFromRaw(raw: unknown, fallbackCategory: BrandInsightCategory): BrandInsight | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  const content = String(record.content ?? "").trim();
  if (!content) return null;

  const now = new Date().toISOString();
  const insightId = String(record.insight_id ?? "").trim() || `insight_${crypto.randomUUID()}`;
  const createdBy = record.created_by === "agent" ? "agent" : "user";

  return {
    insight_id: insightId,
    agent_type: "brand",
    category: normalizeCategory(record.category, fallbackCategory),
    title: String(record.title ?? "").trim(),
    content,
    reason: String(record.reason ?? "").trim(),
    evidence: Array.isArray(record.evidence) ? (record.evidence as BrandInsight["evidence"]) : [],
    confidence: normalizeConfidence(record.confidence),
    status:
      record.status === "confirmed" ||
      record.status === "pending" ||
      record.status === "ignored"
        ? record.status
        : "new",
    created_by: createdBy,
    updated_by: record.updated_by === "agent" ? "agent" : createdBy,
    based_on_script_version_id:
      typeof record.based_on_script_version_id === "string" ? record.based_on_script_version_id : null,
    created_at: String(record.created_at ?? now),
    updated_at: String(record.updated_at ?? now)
  };
}

export function insightsFromProject(project: Project): {
  explicit: BrandInsight[];
  implicit: BrandInsight[];
} {
  const insights = Array.isArray(project.brand_insights) ? project.brand_insights : [];
  const explicit = insights
    .filter((item) => item.category === "explicit_requirement")
    .map((item) => insightFromRaw(item, "explicit_requirement"))
    .filter((item): item is BrandInsight => item !== null);
  const implicit = insights
    .filter((item) => item.category === "implicit_requirement")
    .map((item) => insightFromRaw(item, "implicit_requirement"))
    .filter((item): item is BrandInsight => item !== null);

  return { explicit, implicit };
}

/** @deprecated Use insightsFromProject */
export function requirementsFromProject(project: Project) {
  return insightsFromProject(project);
}

export function createEmptyInsight(category: BrandInsightCategory): BrandInsight {
  const now = new Date().toISOString();
  return {
    insight_id: `insight_${crypto.randomUUID()}`,
    agent_type: "brand",
    category,
    title: "",
    content: "",
    reason: "",
    evidence: [],
    confidence: "medium",
    status: "new",
    created_by: "user",
    updated_by: "user",
    based_on_script_version_id: null,
    created_at: now,
    updated_at: now
  };
}

export function toApiBrandInsights(items: BrandInsight[]) {
  return items
    .map((item) => ({
      insight_id: item.insight_id,
      title: item.title.trim(),
      content: item.content.trim(),
      reason: item.reason.trim(),
      confidence: item.confidence,
      category: item.category,
      status: item.status,
      ...(item.created_by ? { created_by: item.created_by } : {})
    }))
    .filter((item) => item.content.length > 0);
}
