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


class ProjectResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    user_id: str
    title: str
    brief: dict[str, Any]
    current_script: dict[str, Any]
    brand_insights: list[dict[str, Any]]
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
