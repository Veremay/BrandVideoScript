export type SaveStatus = "saved" | "editing" | "saving" | "failed";
export type AgentType = "brand" | "audience" | "expert";
export type BrandInsightCategory = "explicit_requirement" | "implicit_requirement" | "brand_feedback";
export type BrandInsightConfidence = "high" | "medium" | "low";
export type BrandInsightStatus = "new" | "confirmed" | "pending" | "ignored";

export type AgentQuote = {
  text: string;
  row_id?: string;
  column_id?: string;
  selection_start?: number;
  selection_end?: number;
};

export type AgentMessage = {
  _id: string;
  project_id: string;
  user_id: string;
  agent_type: AgentType;
  role: "user" | "assistant" | "system";
  content: string;
  quotes: AgentQuote[];
  created_at: string;
};

export type AgentStreamPayload = {
  user_id: string;
  content: string;
  quotes: AgentQuote[];
};

export type Brief = {
  filename: string | null;
  text: string;
  summary: string;
  parse_status: "pending" | "parsing" | "parsed" | "failed";
  uploaded_at: string | null;
};

export type BrandResearchStatus = "idle" | "running" | "done" | "failed";

export type BrandResearchSnippet = {
  title?: string;
  url?: string;
  snippet?: string;
  path?: string;
  heading?: string;
};

export type BrandPipelineTraceKind =
  | "brief_uploaded"
  | "pipeline_started"
  | "pipeline_completed"
  | "pipeline_failed"
  | "tool_call"
  | "tool_result"
  | "llm_request"
  | "llm_response";

export type BrandPipelineTraceEvent = {
  id: string;
  ts: string;
  kind: BrandPipelineTraceKind;
  source: string;
  run_id: string;
  data: Record<string, unknown>;
};

export type BrandResearch = {
  status: BrandResearchStatus;
  brand_slug: string | null;
  matched_wiki: boolean;
  queries: string[];
  web_snippets: BrandResearchSnippet[];
  wiki_snippets: BrandResearchSnippet[];
  research_summary: string;
  error_message: string | null;
  trace_run_id?: string | null;
  traces?: BrandPipelineTraceEvent[];
  updated_at: string | null;
};

export type BrandInsight = {
  insight_id: string;
  agent_type: "brand";
  category: BrandInsightCategory;
  title: string;
  content: string;
  reason: string;
  evidence: Array<{
    source_type?: "brief" | "pr_feedback" | "script" | "chat" | "web" | "brand_wiki" | string;
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

export type AudienceAnalysisPart = {
  row_id: string;
  reason: string;
};

export type AudienceAnalysis = {
  analysis_id?: string;
  persona_id?: string;
  persona_name?: string;
  based_on_script_updated_at?: string | null;
  summary?: string;
  naturalness_score?: number | null;
  credibility_score?: number | null;
  ad_sensitivity_score?: number | null;
  key_risks?: string[];
  liked_parts?: AudienceAnalysisPart[];
  rejected_parts?: AudienceAnalysisPart[];
  suggestions?: string[];
  updated_at?: string;
};

export type ExpertDirection = "brand_first" | "audience_natural" | "balanced" | "creator_expression" | "custom";
export type ExpertSuggestionStatus = "draft" | "applied" | "partially_applied" | "dismissed";

export type ExpertHunk = {
  hunk_id: string;
  row_id: string;
  column_id: string;
  old: string;
  new: string;
  reason: string;
};

export type ExpertSuggestion = {
  suggestion_id: string;
  title: string;
  direction: ExpertDirection;
  description: string;
  target_problem: string;
  rationale: string;
  brand_tradeoff: string;
  audience_tradeoff: string;
  creator_tradeoff: string;
  risk: string;
  explanation_to_brand: string;
  hunks: ExpertHunk[];
  based_on_brand_insight_ids: string[];
  based_on_audience_analysis_id: string | null;
  status: ExpertSuggestionStatus;
  created_at: string;
  updated_at: string;
};

export type ScriptSnapshotReason =
  | "manual_save"
  | "before_expert_apply"
  | "after_expert_apply"
  | "before_restore"
  | "import";

export type ScriptSnapshotSummary = {
  _id: string;
  project_id: string;
  user_id: string;
  reason: ScriptSnapshotReason;
  suggestion_id: string | null;
  applied_hunk_ids: string[];
  created_at: string;
};

export type ExpertApplyResult = {
  project: Project;
  applied_hunk_ids: string[];
  skipped_hunk_ids: string[];
  conflict_hunk_ids: string[];
  before_snapshot_id: string | null;
  after_snapshot_id: string | null;
  applied_hunk_count: number;
};

export type Project = {
  _id: string;
  user_id: string;
  title: string;
  brief: Brief;
  brand_research?: BrandResearch;
  current_script: Script;
  brand_insights: BrandInsight[];
  personas: Persona[];
  active_persona_id: string | null;
  audience_analysis: AudienceAnalysis;
  expert_suggestions: ExpertSuggestion[];
  stale: Record<AgentType, boolean>;
  created_at: string;
  updated_at: string;
};
