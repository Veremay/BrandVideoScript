"""Pydantic schemas for LLM agent JSON outputs.

These models validate and coerce the raw JSON returned by each agent, catching
field-name typos, wrong types, and missing keys before the data reaches the DB
or the frontend.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


ConfidenceLevel = Literal["high", "medium", "low"]
InsightCategory = Literal["explicit_requirement", "implicit_requirement"]

_VALID_INSIGHT_CATEGORIES: frozenset[str] = frozenset(InsightCategory.__args__)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Brand Agent
# ---------------------------------------------------------------------------


class BrandRequirementItem(BaseModel):
    id: str = Field(default_factory=lambda: f"req_{uuid4().hex[:12]}")
    text: str
    confidence: ConfidenceLevel = "medium"
    evidence: str | None = None

    @field_validator("text", mode="before")
    @classmethod
    def coerce_text(cls, v: Any) -> str:
        return str(v).strip() if v is not None else ""

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> str:
        if str(v).lower() in {"high", "medium", "low"}:
            return str(v).lower()
        return "medium"


class BrandInsightItem(BaseModel):
    category: InsightCategory = "explicit_requirement"
    title: str = ""
    content: str = ""
    reason: str = ""
    confidence: ConfidenceLevel = "medium"

    @field_validator("category", mode="before")
    @classmethod
    def coerce_category(cls, v: Any) -> str:
        normalized = str(v).strip().lower() if v else ""
        if normalized in _VALID_INSIGHT_CATEGORIES:
            return normalized
        return "explicit_requirement"

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> str:
        if str(v).lower() in {"high", "medium", "low"}:
            return str(v).lower()
        return "medium"


class IbisNodeItem(BaseModel):
    node_type: str = "position"
    title: str = ""
    content: str = ""
    source_type: str = "brand_brief"
    source_perspective: str = "brand"


class IbisOutput(BaseModel):
    nodes: list[IbisNodeItem] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    external_edges: list[dict[str, Any]] = Field(default_factory=list)
    node_updates: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("nodes", "edges", "external_edges", "node_updates", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> list:
        return v if isinstance(v, list) else []


def _coerce_requirements(v: Any) -> list:
    """Shared validator: accept plain strings or dicts; skip nulls."""
    if not isinstance(v, list):
        return []
    result = []
    for item in v:
        if isinstance(item, str) and item.strip():
            result.append({"text": item.strip(), "confidence": "medium"})
        elif isinstance(item, dict) and item.get("text"):
            result.append(item)
    return result


def _coerce_string_list(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(item).strip() for item in v if item]


class BrandRequirementsOutput(BaseModel):
    """Phase 1 output: requirements extraction only (no ibis)."""

    explicit_requirements: list[BrandRequirementItem] = Field(default_factory=list)
    implicit_requirements: list[BrandRequirementItem] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    pr_risks: list[str] = Field(default_factory=list)
    brand_insights: list[BrandInsightItem] = Field(default_factory=list)

    @field_validator("explicit_requirements", "implicit_requirements", mode="before")
    @classmethod
    def coerce_requirements(cls, v: Any) -> list:
        return _coerce_requirements(v)

    @field_validator("constraints", "pr_risks", mode="before")
    @classmethod
    def coerce_string_list(cls, v: Any) -> list[str]:
        return _coerce_string_list(v)

    @field_validator("brand_insights", mode="before")
    @classmethod
    def coerce_insights(cls, v: Any) -> list:
        return v if isinstance(v, list) else []

    @model_validator(mode="before")
    @classmethod
    def accept_root(cls, v: Any) -> Any:
        if isinstance(v, dict) and set(v.keys()) == {"result"}:
            return v["result"]
        return v


class BrandIbisOutput(BaseModel):
    """Phase 2 output: IBIS node generation only (no requirements)."""

    ibis: IbisOutput = Field(default_factory=IbisOutput)

    @model_validator(mode="before")
    @classmethod
    def accept_root(cls, v: Any) -> Any:
        if isinstance(v, dict) and set(v.keys()) == {"result"}:
            return v["result"]
        return v


class BrandAgentOutput(BaseModel):
    """Combined output (kept for backward compatibility / mock fallback)."""

    explicit_requirements: list[BrandRequirementItem] = Field(default_factory=list)
    implicit_requirements: list[BrandRequirementItem] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    pr_risks: list[str] = Field(default_factory=list)
    brand_insights: list[BrandInsightItem] = Field(default_factory=list)
    ibis: IbisOutput = Field(default_factory=IbisOutput)

    @field_validator("explicit_requirements", "implicit_requirements", mode="before")
    @classmethod
    def coerce_requirements(cls, v: Any) -> list:
        return _coerce_requirements(v)

    @field_validator("constraints", "pr_risks", mode="before")
    @classmethod
    def coerce_string_list(cls, v: Any) -> list[str]:
        return _coerce_string_list(v)

    @field_validator("brand_insights", mode="before")
    @classmethod
    def coerce_insights(cls, v: Any) -> list:
        return v if isinstance(v, list) else []

    @model_validator(mode="before")
    @classmethod
    def accept_root(cls, v: Any) -> Any:
        if isinstance(v, dict) and set(v.keys()) == {"result"}:
            return v["result"]
        return v
