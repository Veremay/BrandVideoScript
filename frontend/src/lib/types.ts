export type SaveStatus = "saved" | "editing" | "saving" | "failed";
export type AgentType = "brand" | "audience" | "expert";
export type BrandInsightCategory = "explicit_requirement" | "implicit_requirement" | "brand_feedback";
export type BrandInsightConfidence = "high" | "medium" | "low";
export type BrandInsightStatus = "new" | "confirmed" | "pending" | "ignored";

export type Brief = {
  filename: string | null;
  text: string;
  summary: string;
  parse_status: "pending" | "parsing" | "parsed" | "failed";
  uploaded_at: string | null;
};

export type BrandInsight = {
  insight_id: string;
  agent_type: "brand";
  category: BrandInsightCategory;
  title: string;
  content: string;
  reason: string;
  evidence: Array<{
    source_type?: "brief" | "pr_feedback" | "script" | "chat" | string;
    quote?: string;
    row_id?: string;
    column_id?: string;
  }>;
  confidence: BrandInsightConfidence;
  status: BrandInsightStatus;
  created_by: "agent" | "user";
  updated_by: "agent" | "user";
  based_on_script_version_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ScriptColumn = {
  column_id: string;
  key: string;
  label: string;
  type: "duration" | "text" | "textarea" | "tag";
  multiline: boolean;
  order: number;
};

export type ScriptCell = {
  column_id: string;
  value: string;
};

export type ScriptRow = {
  row_id: string;
  order: number;
  cells: ScriptCell[];
};

export type Script = {
  columns: ScriptColumn[];
  rows: ScriptRow[];
  updated_at?: string;
};

export type PersonaAdSensitivity = "low" | "medium" | "high";

export type Persona = {
  persona_id: string;
  name: string;
  icon: string;
  gender: string;
  age_range: string;
  preferences: string;
  behavior: string;
  platform_context: string;
  ad_sensitivity: PersonaAdSensitivity;
  trust_trigger: string[];
  reject_trigger: string[];
  data_source: "manual" | "system_generated" | "imported_data";
  created_at: string;
  updated_at: string;
};

export type Project = {
  _id: string;
  user_id: string;
  title: string;
  brief: Brief;
  current_script: Script;
  brand_insights: BrandInsight[];
  personas: Persona[];
  active_persona_id: string | null;
  audience_analysis: Record<string, unknown>;
  expert_suggestions: Array<Record<string, unknown>>;
  stale: Record<AgentType, boolean>;
  created_at: string;
  updated_at: string;
};
