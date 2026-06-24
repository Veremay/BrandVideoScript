from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UserEnterRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)


class UserResponse(BaseModel):
    user_id: str
    created_at: str


VideoCategory = Literal["lifestyle"]


class ProjectCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    title: str = Field(default="未命名项目", min_length=1, max_length=120)
    video_category: VideoCategory = "lifestyle"


class ProjectUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=120)


class ScriptPatchRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    script: dict[str, Any]


class ScriptCellPatchRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    row_id: str = Field(min_length=1)
    column_id: str = Field(min_length=1)
    value: str = ""


class ScriptRowCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    after_row_id: str | None = None


class ScriptColumnCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    after_column_id: str | None = None
    label: str = Field(default="新列", min_length=1, max_length=40)
    type: Literal["duration", "text", "textarea", "tag"] = "text"
    multiline: bool = False


class ScriptColumnUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=40)


class ScriptSnapshotCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    reason: Literal[
        "manual_save",
        "auto_save",
        "before_map_update",
        "before_expert_apply",
        "after_expert_apply",
        "brand_feedback_sync",
        "import",
        "rollback",
    ] = "manual_save"


class ScriptSnapshotSummary(BaseModel):
    snapshot_id: str
    project_id: str
    reason: str
    script_version_id: str | None = None
    created_at: str


class ScriptSnapshotListResponse(BaseModel):
    snapshots: list[ScriptSnapshotSummary]


class ScriptSnapshotCreateResponse(BaseModel):
    snapshot: ScriptSnapshotSummary


class BriefUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1)
    filename: str | None = Field(default=None, max_length=180)


class BrandInsightCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    category: Literal["explicit_requirement", "implicit_requirement", "brand_feedback"]
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)
    reason: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    status: Literal["new", "confirmed", "pending", "ignored"] = "new"
    created_by: Literal["agent", "user"] = "user"


class BrandInsightUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    category: Literal["explicit_requirement", "implicit_requirement", "brand_feedback"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1)
    reason: str | None = None
    evidence: list[dict[str, Any]] | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    status: Literal["new", "confirmed", "pending", "ignored"] | None = None


class BrandRequirementItem(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    text: str = Field(min_length=1, max_length=2000)
    evidence: str | None = Field(default=None, max_length=2000)
    confidence: Literal["high", "medium", "low"] = "medium"
    source: Literal["user", "agent"] | None = None


class BrandRequirementsUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    explicit_requirements: list[BrandRequirementItem] = Field(default_factory=list)
    implicit_requirements: list[BrandRequirementItem] = Field(default_factory=list)


class PersonaCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    icon: str = Field(default="", max_length=8)
    gender: str = Field(default="", max_length=40)
    age_range: str = Field(default="", max_length=60)
    preferences: str = Field(default="", max_length=600)
    behavior: str = Field(default="", max_length=600)
    platform_context: str = Field(default="", max_length=200)
    ad_sensitivity: Literal["low", "medium", "high"] = "medium"
    trust_trigger: list[str] | str = Field(default_factory=list)
    reject_trigger: list[str] | str = Field(default_factory=list)


class PersonaUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    gender: str | None = Field(default=None, max_length=40)
    age_range: str | None = Field(default=None, max_length=60)
    preferences: str | None = Field(default=None, max_length=600)
    behavior: str | None = Field(default=None, max_length=600)
    platform_context: str | None = Field(default=None, max_length=200)
    ad_sensitivity: Literal["low", "medium", "high"] | None = None
    trust_trigger: list[str] | str | None = None
    reject_trigger: list[str] | str | None = None


class ActivePersonaUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    persona_id: str | None = None


class BriefParseRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)


class PersonaProvisionRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    platform_context: Literal["xiaohongshu", "douyin", "bilibili", "other"] = "xiaohongshu"
    content_category: str | None = Field(default=None, max_length=120)
    brand_name: str | None = Field(default=None, max_length=120)
    video_topic: str | None = Field(default=None, max_length=200)
    run_audience_parse: bool = True


class GraphResponse(BaseModel):
    rationale_nodes: list[dict[str, Any]] = Field(default_factory=list)
    rationale_edges: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: str


class BriefParseResponse(BaseModel):
    project: dict[str, Any]
    parse_summary: dict[str, Any]


class PersonaProvisionResponse(BaseModel):
    personas: list[dict[str, Any]]
    active_persona_id: str | None
    analytics_meta: dict[str, Any] | None = None
    project: dict[str, Any] | None = None
    audience_parse: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    user_id: str
    title: str
    video_category: str = "lifestyle"
    platform_context: str = "other"
    brief: dict[str, Any]
    current_script: dict[str, Any]
    brand_insights: list[dict[str, Any]]
    brand_perspective_result: dict[str, Any] | None = None
    audience_perspective_result: dict[str, Any] | None = None
    expert_perspective_result: dict[str, Any] | None = None
    rationale_nodes: list[dict[str, Any]] = Field(default_factory=list)
    rationale_edges: list[dict[str, Any]] = Field(default_factory=list)
    consideration_queue: list[str] = Field(default_factory=list)
    communication_support_queue: list[str] = Field(default_factory=list)
    negotiation_preparation: dict[str, Any] | None = None
    modification_schemes: list[dict[str, Any]] = Field(default_factory=list)
    personas: list[dict[str, Any]]
    active_persona_id: str | None
    audience_analysis: dict[str, Any]
    expert_suggestions: list[dict[str, Any]]
    current_script_version_id: str | None = None
    stale: dict[str, str]
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


class LLMChatRequest(BaseModel):
    messages: list[dict[str, str]]
    task_type: str = "general_chat"
    stream: bool = False
    response_format: dict[str, Any] | None = None
    complexity: Literal["normal", "high"] = "normal"


class TavilySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    max_results: int = Field(default=5, ge=1, le=20)
    search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "basic"
    topic: Literal["general", "news", "finance"] | None = None
    time_range: Literal["day", "week", "month", "year"] | None = None
    include_domains: list[str] | None = None
    exclude_domains: list[str] | None = None
    include_answer: bool | Literal["basic", "advanced"] = False
    include_raw_content: bool | Literal["markdown", "text"] = False
    mock: bool = False


class TavilyExtractRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=20)
    extract_depth: Literal["basic", "advanced"] = "basic"
    format: Literal["markdown", "text"] = "markdown"
    query: str | None = Field(default=None, max_length=400)
    mock: bool = False


class CoordinatorQuote(BaseModel):
    text: str = Field(min_length=1)
    row_id: str | None = None
    column_id: str | None = None
    selection_start: int | None = None
    selection_end: int | None = None
    script_version_id: str | None = None


class CoordinatorStreamRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=4000)
    task_type: Literal[
        "user_message",
        "quote_analysis",
        "script_delta",
        "generate_modification_schemes",
    ] = "user_message"
    requested_perspectives: list[Literal["brand", "audience", "expert", "comprehensive"]] = Field(default_factory=lambda: ["comprehensive"])
    quotes: list[CoordinatorQuote] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)
    changed_row_ids: list[str] = Field(default_factory=list)
    # "full": multi-agent IBIS pipeline. "vanilla": single LLM with a system prompt only.
    mode: Literal["full", "vanilla"] = "full"


class CoordinatorMessageResponse(BaseModel):
    message_id: str
    project_id: str
    user_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    task_type: str
    requested_perspectives: list[str] = Field(default_factory=list)
    active_persona_id: str | None = None
    quotes: list[dict[str, Any]] = Field(default_factory=list)
    related_node_ids: list[str] = Field(default_factory=list)
    generated_artifact_ids: list[str] = Field(default_factory=list)
    created_at: str


class CoordinatorMessageListResponse(BaseModel):
    messages: list[CoordinatorMessageResponse]


class ScriptRefLink(BaseModel):
    row_id: str
    column_id: str | None = None
    text_snapshot: str = ""
    script_version_id: str | None = None


class GraphNodeCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    node_type: Literal["issue", "position", "argument", "reference"] = "issue"
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=2000)
    source_type: Literal[
        "brand_brief",
        "brand_feedback",
        "brand_inferred",
        "audience_persona",
        "audience_simulation",
        "expert_strategy",
        "creator_manual",
        "external_reference",
    ] = "creator_manual"
    source_perspective: str = "creator"
    layout: dict[str, float] | None = None
    status: Literal[
        "open", "in_review", "resolved", "needs_negotiation", "to_be_considered", "deferred", "dismissed"
    ] = "open"
    linked_script_refs: list[ScriptRefLink] = Field(default_factory=list)


class GraphNodeUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    status: Literal[
        "open", "in_review", "resolved", "needs_negotiation", "to_be_considered", "deferred", "dismissed"
    ] | None = None
    layout: dict[str, float] | None = None


class GraphEdgeCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    from_node_id: str = Field(min_length=1)
    to_node_id: str = Field(min_length=1)
    relation_type: Literal[
        "responds_to",
        "supports",
        "opposes",
        "evidenced_by",
        "derived_from",
        "refines",
        "conflicts_with",
        "updates",
    ] = "responds_to"


class GraphNodeConsiderationRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    in_queue: bool


class CommunicationSupportToggleRequest(BaseModel):
    """Argue a brand feedback row (add/remove it from the communication support list)."""

    user_id: str = Field(min_length=1, max_length=80)
    row_id: str = Field(min_length=1)
    column_id: str = Field(min_length=1)
    in_list: bool


class NegotiationGenerateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    message: str | None = Field(default=None, max_length=2000)


class NegotiationGenerateResponse(BaseModel):
    project: dict[str, Any]
    negotiation_preparation: dict[str, Any] | None = None
    assistant_reply: str = ""


class GraphNodeLayoutItem(BaseModel):
    node_id: str = Field(min_length=1)
    layout: dict[str, float]


class GraphLayoutsBatchUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    layouts: list[GraphNodeLayoutItem] = Field(min_length=1)
    skip_snapshot: bool = False


class GraphSyncFromScriptRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    changed_row_ids: list[str] = Field(default_factory=list)


class GraphSyncFromScriptResponse(BaseModel):
    project: dict[str, Any]
    nodes_added: int = 0
    node_updates: int = 0
    assistant_reply: str = ""


class ModificationSchemeHunk(BaseModel):
    hunk_id: str
    row_id: str
    column_id: str
    context: str = ""
    removed: str
    added: str


class ModificationSchemeItem(BaseModel):
    scheme_id: str
    project_id: str
    title: str
    direction: Literal["conservative", "balanced", "creator_led", "audience_friendly", "custom"]
    target_issue_ids: list[str] = Field(default_factory=list)
    target_position_ids: list[str] = Field(default_factory=list)
    changes_summary: str = ""
    rationale: str = ""
    tradeoffs: dict[str, str] = Field(default_factory=dict)
    sacrifice: str = ""
    communication_scene: str = ""
    brand_objection: str = ""
    response_script: str = ""
    risk: str = ""
    hunks: list[ModificationSchemeHunk] = Field(default_factory=list)
    related_node_ids: list[str] = Field(default_factory=list)
    based_on_script_version_id: str | None = None
    status: Literal["draft", "previewed", "partially_applied", "applied", "dismissed"] = "draft"
    created_at: str


class ModificationSchemeListResponse(BaseModel):
    schemes: list[ModificationSchemeItem]


class ModificationSchemeGenerateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    target_issue_ids: list[str] = Field(default_factory=list)
    target_position_ids: list[str] = Field(default_factory=list)
    message: str | None = Field(default=None, max_length=2000)


class ModificationSchemeGenerateResponse(BaseModel):
    project: dict[str, Any]
    schemes: list[ModificationSchemeItem]
    assistant_reply: str = ""


class ModificationSchemeApplyRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    accepted_hunk_ids: list[str] = Field(default_factory=list)
    rejected_hunk_ids: list[str] = Field(default_factory=list)


class ModificationSchemeApplyResponse(BaseModel):
    project: dict[str, Any]
    applied_hunk_ids: list[str]
    applied_hunk_count: int
    conflicts: list[dict[str, str]] = Field(default_factory=list)


class ShareCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)


class ShareCreateResponse(BaseModel):
    share_token: str
    expires_at: str | None = None


class ShareScriptResponse(BaseModel):
    title: str
    script: dict[str, Any]
    expires_at: str | None = None


class ShareFeedbackPatchRequest(BaseModel):
    row_id: str = Field(min_length=1)
    column_id: str = Field(min_length=1)
    value: str = ""


class ShareFeedbackPatchResponse(BaseModel):
    script: dict[str, Any]
