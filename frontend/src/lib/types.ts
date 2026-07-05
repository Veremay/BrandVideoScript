export type SaveStatus = "saved" | "editing" | "saving" | "failed";

export type StaleStatus =
  | "up_to_date"
  | "stale_script_changed"
  | "stale_brief_changed"
  | "stale_persona_changed"
  | "stale_graph_changed"
  | "stale_brand_feedback"
  | "generating"
  | "failed";

export type ArtifactKey = "rationale_graph" | "modification_schemes" | "negotiation_preparation";

export type ArtifactStaleness = Record<ArtifactKey, StaleStatus>;

export type ScriptSnapshotReason =
  | "manual_save"
  | "auto_save"
  | "before_map_update"
  | "before_expert_apply"
  | "after_expert_apply"
  | "brand_feedback_sync"
  | "import"
  | "rollback";

export type ScriptSnapshotSummary = {
  snapshot_id: string;
  project_id: string;
  reason: ScriptSnapshotReason;
  script_version_id: string | null;
  created_at: string;
};
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

export type BrandRequirementConfidence = "high" | "medium" | "low";

export type BrandRequirement = {
  id: string;
  text: string;
  evidence?: string;
  confidence: BrandRequirementConfidence;
  source?: "user" | "agent";
};

export type BrandPerspectiveResult = {
  constraints?: string[];
  pr_risks?: string[];
  tool_calls_used?: string[];
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
  analytics_meta?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type RequestedPerspective = "brand" | "audience" | "expert" | "comprehensive";

export type CoordinatorQuote = {
  text: string;
  row_id?: string;
  column_id?: string;
  selection_start?: number;
  selection_end?: number;
  script_version_id?: string;
};

export type CoordinatorMessage = {
  message_id: string;
  project_id: string;
  user_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  task_type: string;
  requested_perspectives: RequestedPerspective[];
  active_persona_id?: string | null;
  quotes: CoordinatorQuote[];
  related_node_ids: string[];
  generated_artifact_ids: string[];
  created_at: string;
};

export type ScriptRefLink = {
  row_id: string;
  column_id?: string;
  text_snapshot?: string;
  script_version_id?: string;
};

export type IssueStatus =
  | "open"
  | "in_review"
  | "resolved"
  | "needs_negotiation"
  | "to_be_considered"
  | "deferred"
  | "dismissed";

export type RationaleSourceType =
  | "brand_brief"
  | "brand_feedback"
  | "brand_inferred"
  | "audience_persona"
  | "audience_simulation"
  | "expert_strategy"
  | "creator_manual"
  | "external_reference";

export type RationaleNodeType = "issue" | "position" | "argument" | "reference";

export type RationaleNode = {
  node_id: string;
  project_id: string;
  node_type: RationaleNodeType;
  title: string;
  content: string;
  source_type: RationaleSourceType;
  source_perspective: string;
  layout?: { x: number; y: number };
  status?: IssueStatus;
  in_consideration_queue?: boolean;
  /** @deprecated Use in_consideration_queue on Position nodes */
  in_negotiation_queue?: boolean;
  /** Brand feedback position is on the creator's communication support list. */
  in_communication_support_queue?: boolean;
  linked_script_refs?: ScriptRefLink[];
  created_by: string;
  updated_at: string;
  /** Reconcile lifecycle: active | resolved (issue conflict gone) | superseded (replaced). */
  lifecycle?: "active" | "resolved" | "superseded";
  /** Transient marker from the latest "update map" pass. */
  change_mark?: "none" | "modified" | "new";
  predecessor_id?: string | null;
  resolved_at?: string | null;
  /** Non-binding hint for user-owned nodes (e.g. "resolved?" / "modify?"). */
  suggestion?: string | null;
  /**
   * Conflict group tags assigned by the Coordinator (e.g. ["A", "B"]).
   * Only meaningful on position nodes. Two positions sharing a tag are in conflict.
   * Tags may span different issues.
   */
  conflict_tags?: string[];
};

export type RationaleEdge = {
  edge_id: string;
  project_id: string;
  from_node_id: string;
  to_node_id: string;
  relation_type: string;
};

export type ModificationSchemeDirection =
  | "conservative"
  | "balanced"
  | "creator_led"
  | "audience_friendly"
  | "custom";

export type ModificationSchemeStatus =
  | "draft"
  | "previewed"
  | "partially_applied"
  | "applied"
  | "dismissed";

export type HunkDecisionState = "pending" | "accepted" | "rejected";

export type ModificationSchemeHunk = {
  hunk_id: string;
  row_id: string;
  column_id: string;
  context?: string;
  removed: string;
  added: string;
  decision?: HunkDecisionState;
  applied_at?: string | null;
};

export type ModificationScheme = {
  scheme_id: string;
  project_id: string;
  title: string;
  direction: ModificationSchemeDirection;
  target_issue_ids: string[];
  target_position_ids?: string[];
  changes_summary: string;
  rationale: string;
  tradeoffs: { brand?: string; audience?: string; creator?: string };
  sacrifice: string;
  communication_scene: string;
  brand_objection: string;
  response_script: string;
  risk: string;
  hunks: ModificationSchemeHunk[];
  related_node_ids: string[];
  based_on_script_version_id: string | null;
  status: ModificationSchemeStatus;
  created_at: string;
};

export type ChoiceHistory = {
  adopted_positions: Array<{
    position_id: string;
    first_considered_at?: string;
    last_considered_at?: string;
    last_used_for_scheme_at?: string | null;
    used_scheme_ids?: string[];
    status_at_use?: string;
    title_snapshot?: string;
    content_snapshot?: string;
    source_type?: string;
    source_perspective?: string;
  }>;
  scheme_position_links: Array<{
    scheme_id: string;
    title?: string;
    direction?: string;
    target_position_ids: string[];
    created_at?: string;
  }>;
};

export type HunkDecision = true | false | null;

export type NegotiationDispute = {
  issue_node_id: string;
  summary: string;
  our_position: string;
  acceptable_concession: string;
  non_negotiable_line: string;
  talking_points: string[];
  related_node_ids: string[];
  related_script_refs: ScriptRefLink[];
};

export type NegotiationPreparation = {
  prep_id: string;
  project_id: string;
  title: string;
  based_on_script_version_id: string | null;
  design_intent: string;
  satisfied_brand_needs: string[];
  open_disputes: NegotiationDispute[];
  recommended_communication_order: string[];
  related_issue_ids: string[];
  status: "draft" | "reviewed" | "exported";
  created_at: string;
  updated_at: string;
};

export type PlatformContext = "xiaohongshu" | "douyin" | "bilibili" | "other";

export type VideoCategory = "lifestyle";

export type Project = {
  _id: string;
  user_id: string;
  title: string;
  video_category?: VideoCategory;
  platform_context?: PlatformContext;
  brief: Brief;
  current_script: Script;
  brand_insights: BrandInsight[];
  brand_perspective_result?: BrandPerspectiveResult | null;
  audience_perspective_result?: Record<string, unknown> | null;
  expert_perspective_result?: Record<string, unknown> | null;
  rationale_nodes?: RationaleNode[];
  rationale_edges?: RationaleEdge[];
  consideration_queue?: string[];
  /** @deprecated Use consideration_queue */
  negotiation_queue?: string[];
  /** Brand feedback positions the creator is arguing (communication support list). */
  communication_support_queue?: string[];
  choice_history?: ChoiceHistory;
  negotiation_preparation?: NegotiationPreparation | null;
  modification_schemes?: ModificationScheme[];
  personas: Persona[];
  active_persona_id: string | null;
  audience_analysis: Record<string, unknown>;
  expert_suggestions: Array<Record<string, unknown>>;
  current_script_version_id?: string | null;
  stale: ArtifactStaleness;
  created_at: string;
  updated_at: string;
};
