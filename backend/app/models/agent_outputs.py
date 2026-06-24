"""Pydantic schemas for LLM agent JSON outputs.

These models validate and coerce the raw JSON returned by each agent, catching
field-name typos, wrong types, and missing keys before the data reaches the DB
or the frontend.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ConfidenceLevel = Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Brand Agent
# ---------------------------------------------------------------------------


class BrandRequirementItem(BaseModel):
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
    category: str = "explicit_requirement"
    title: str = ""
    content: str = ""
    reason: str = ""
    confidence: ConfidenceLevel = "medium"

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


class BrandAgentOutput(BaseModel):
    explicit_requirements: list[BrandRequirementItem] = Field(default_factory=list)
    implicit_requirements: list[BrandRequirementItem] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    pr_risks: list[str] = Field(default_factory=list)
    brand_insights: list[BrandInsightItem] = Field(default_factory=list)
    ibis: IbisOutput = Field(default_factory=IbisOutput)

    @field_validator("explicit_requirements", "implicit_requirements", mode="before")
    @classmethod
    def coerce_requirements(cls, v: Any) -> list:
        """Accept plain strings or dicts; skip nulls."""
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, str) and item.strip():
                result.append({"text": item.strip(), "confidence": "medium"})
            elif isinstance(item, dict) and item.get("text"):
                result.append(item)
        return result

    @field_validator("constraints", "pr_risks", mode="before")
    @classmethod
    def coerce_string_list(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(item).strip() for item in v if item]

    @field_validator("brand_insights", mode="before")
    @classmethod
    def coerce_insights(cls, v: Any) -> list:
        return v if isinstance(v, list) else []

    @model_validator(mode="before")
    @classmethod
    def accept_root(cls, v: Any) -> Any:
        """If the LLM wraps the whole output in a key, unwrap it."""
        if isinstance(v, dict) and set(v.keys()) == {"result"}:
            return v["result"]
        return v
