from datetime import UTC, datetime
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


BRAND_FEEDBACK_COLUMN_KEY = "feedback"
SCRIPT_MODES = {"full", "vanilla"}


def script_settings(mode: str = "full") -> dict:
    normalized_mode = mode if mode in SCRIPT_MODES else "full"
    return {
        "mode": normalized_mode,
        "system_support_enabled": normalized_mode == "full",
    }


def default_columns() -> list[dict]:
    return [
        {
            "column_id": "col_duration",
            "key": "duration",
            "label": "Duration (s)",
            "type": "duration",
            "multiline": False,
            "order": 0,
        },
        {
            "column_id": "col_scene",
            "key": "scene",
            "label": "Visual",
            "type": "textarea",
            "multiline": True,
            "order": 1,
        },
        {
            "column_id": "col_format",
            "key": "format",
            "label": "Format / Script",
            "type": "textarea",
            "multiline": True,
            "order": 2,
        },
        {
            "column_id": "col_notes",
            "key": "notes",
            "label": "Remarks",
            "type": "text",
            "multiline": False,
            "order": 3,
        },
        {
            "column_id": "col_feedback",
            "key": BRAND_FEEDBACK_COLUMN_KEY,
            "label": "Brand Feedback",
            "type": "textarea",
            "multiline": True,
            "order": 4,
        },
    ]


def empty_row(order: int = 0) -> dict:
    return {
        "row_id": new_id("row"),
        "order": order,
        "cells": [{"column_id": column["column_id"], "value": ""} for column in default_columns()],
    }


def default_script(mode: str = "full") -> dict:
    return {
        "settings": script_settings(mode),
        "columns": default_columns(),
        "rows": [empty_row()],
        "updated_at": now_iso(),
    }
