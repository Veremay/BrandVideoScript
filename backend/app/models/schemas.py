from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UserEnterRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)


class UserResponse(BaseModel):
    user_id: str
    created_at: str


class ProjectCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    title: str = Field(default="未命名项目", min_length=1, max_length=120)


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


class PersonaCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    gender: str = Field(default="", max_length=40)
    age_range: str = Field(default="", max_length=60)
    preferences: str = Field(default="", max_length=600)
    behavior: str = Field(default="", max_length=600)
    platform_context: str = Field(default="", max_length=200)
    ad_sensitivity: Literal["low", "medium", "high"] = "medium"
    trust_trigger: list[str] = Field(default_factory=list)
    reject_trigger: list[str] = Field(default_factory=list)


class PersonaUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    gender: str | None = Field(default=None, max_length=40)
    age_range: str | None = Field(default=None, max_length=60)
    preferences: str | None = Field(default=None, max_length=600)
    behavior: str | None = Field(default=None, max_length=600)
    platform_context: str | None = Field(default=None, max_length=200)
    ad_sensitivity: Literal["low", "medium", "high"] | None = None
    trust_trigger: list[str] | None = None
    reject_trigger: list[str] | None = None


class ActivePersonaUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    persona_id: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    user_id: str
    title: str
    brief: dict[str, Any]
    current_script: dict[str, Any]
    brand_insights: list[dict[str, Any]]
    brand_research: dict[str, Any] = Field(default_factory=dict)
    personas: list[dict[str, Any]]
    active_persona_id: str | None
    audience_analysis: dict[str, Any]
    expert_suggestions: list[dict[str, Any]]
    stale: dict[str, bool]
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


class AgentQuoteRequest(BaseModel):
    text: str = Field(min_length=1)
    row_id: str | None = None
    column_id: str | None = None
    selection_start: int | None = None
    selection_end: int | None = None


class AgentStreamRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1)
    quotes: list[AgentQuoteRequest] = Field(default_factory=list)


class AgentMessageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    project_id: str
    user_id: str
    agent_type: Literal["brand", "audience", "expert"]
    role: Literal["user", "assistant", "system"]
    content: str
    quotes: list[dict[str, Any]]
    created_at: str


class AgentMessagesResponse(BaseModel):
    messages: list[AgentMessageResponse]
