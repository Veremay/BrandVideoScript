"""Artifact staleness markers (MVP). See docs/data_structures.md §12."""

from typing import Literal

StaleStatus = Literal[
    "up_to_date",
    "stale_script_changed",
    "stale_brief_changed",
    "stale_persona_changed",
    "stale_graph_changed",
    "stale_brand_feedback",
    "generating",
    "failed",
]

ARTIFACT_KEYS = ("rationale_graph", "modification_schemes", "negotiation_preparation")


def default_stale() -> dict[str, str]:
    return {key: "up_to_date" for key in ARTIFACT_KEYS}


def mark_script_changed() -> dict[str, str]:
    return {key: "stale_script_changed" for key in ARTIFACT_KEYS}


def mark_brief_changed() -> dict[str, str]:
    return {
        "rationale_graph": "stale_brief_changed",
        "modification_schemes": "stale_graph_changed",
        "negotiation_preparation": "stale_graph_changed",
    }


def mark_persona_changed() -> dict[str, str]:
    return {
        "rationale_graph": "stale_persona_changed",
        "modification_schemes": "stale_persona_changed",
        "negotiation_preparation": "up_to_date",
    }


def stale_set_fields(updates: dict[str, str]) -> dict[str, str]:
    return {f"stale.{key}": value for key, value in updates.items()}


def is_artifact_stale(stale: dict | None, key: str) -> bool:
    if not stale:
        return False
    value = stale.get(key)
    return isinstance(value, str) and value.startswith("stale_")
