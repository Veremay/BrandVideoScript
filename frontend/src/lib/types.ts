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

export type BrandResearch = {
  status: BrandResearchStatus;
  brand_slug: string | null;
  matched_wiki: boolean;
  queries: string[];
  web_snippets: BrandResearchSnippet[];
  wiki_snippets: BrandResearchSnippet[];
  research_summary: string;
  error_message: string | null;
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

export type Project = {
  _id: string;
  user_id: string;
  title: string;
  brief: Brief;
  brand_research?: BrandResearch;
  current_script: Script;
  brand_insights: BrandInsight[];
  personas: Array<Record<string, unknown>>;
  active_persona_id: string | null;
  audience_analysis: Record<string, unknown>;
  expert_suggestions: Array<Record<string, unknown>>;
  stale: Record<AgentType, boolean>;
  created_at: string;
  updated_at: string;
};
