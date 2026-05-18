export type SaveStatus = "saved" | "editing" | "saving" | "failed";
export type AgentType = "brand" | "audience" | "expert";

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
  brief: Record<string, unknown>;
  current_script: Script;
  brand_insights: Array<Record<string, unknown>>;
  personas: Array<Record<string, unknown>>;
  active_persona_id: string | null;
  audience_analysis: Record<string, unknown>;
  expert_suggestions: Array<Record<string, unknown>>;
  stale: Record<AgentType, boolean>;
  created_at: string;
  updated_at: string;
};

