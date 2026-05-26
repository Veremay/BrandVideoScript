from datetime import UTC, datetime
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


BRAND_FEEDBACK_COLUMN_KEY = "feedback"


def default_columns() -> list[dict]:
    return [
        {
            "column_id": "col_duration",
            "key": "duration",
            "label": "时长",
            "type": "duration",
            "multiline": False,
            "order": 0,
        },
        {
            "column_id": "col_scene",
            "key": "scene",
            "label": "画面",
            "type": "textarea",
            "multiline": True,
            "order": 1,
        },
        {
            "column_id": "col_format",
            "key": "format",
            "label": "形式",
            "type": "text",
            "multiline": False,
            "order": 2,
        },
        {
            "column_id": "col_notes",
            "key": "notes",
            "label": "备注",
            "type": "text",
            "multiline": False,
            "order": 3,
        },
        {
            "column_id": "col_feedback",
            "key": BRAND_FEEDBACK_COLUMN_KEY,
            "label": "品牌反馈",
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


def default_script() -> dict:
    return {
        "columns": default_columns(),
        "rows": [empty_row()],
        "updated_at": now_iso(),
    }
