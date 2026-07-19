from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.models.script import BRAND_FEEDBACK_COLUMN_KEY
from app.services.prompt_loader import load_prompt, render_prompt


def feedback_cell_value(script: dict[str, Any], row_id: str, column_id: str) -> str:
    for row in script.get("rows", []):
        if row.get("row_id") != row_id:
            continue
        for cell in row.get("cells", []):
            if cell.get("column_id") == column_id:
                return str(cell.get("value", "")).strip()
    return ""


def assert_feedback_column(script: dict[str, Any], column_id: str) -> None:
    for column in script.get("columns", []):
        if column.get("column_id") == column_id:
            if column.get("key") != BRAND_FEEDBACK_COLUMN_KEY:
                raise ValueError("Only the brand feedback column can be used for argue prompts")
            return
    raise ValueError("Brand feedback column not found")


def scene_number_for_row(script: dict[str, Any], row_id: str) -> int:
    rows = sorted(script.get("rows") or [], key=lambda row: row.get("order", 0))
    for index, row in enumerate(rows, start=1):
        if row.get("row_id") == row_id:
            return index
    raise ValueError("Script row not found")


def format_argue_item(scene_number: int, feedback: str) -> str:
    text = feedback.strip()
    if not text:
        raise ValueError("This row has no brand feedback to argue")
    if get_settings().prompt_language == "en":
        return f"Scene {scene_number}, {text}"
    return f"第{scene_number}幕，{text}"


def build_vanilla_argue_prompt(scene_number: int, feedback: str) -> str:
    item = format_argue_item(scene_number, feedback)
    template = load_prompt("vanilla_argue_prompt.md")
    return render_prompt(template, {"items": item}).strip()


def build_vanilla_argue_append_block(scene_number: int, feedback: str) -> str:
    item = format_argue_item(scene_number, feedback)
    template = load_prompt("vanilla_argue_append.md")
    return render_prompt(template, {"item": item}).strip()
