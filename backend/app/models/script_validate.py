"""Validate and normalize current_script JSON (Phase 1 schema gate)."""

import re
from copy import deepcopy
from math import isfinite

from app.models.script import BRAND_FEEDBACK_COLUMN_KEY

ALLOWED_COLUMN_TYPES = {"duration", "text", "textarea", "tag"}


def _clear_legacy_duration(value: str) -> str:
    """Discard the retired start-end format instead of guessing a duration."""
    return "" if re.fullmatch(r"\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*", value) else value


def _valid_duration_value(value: str) -> bool:
    normalized = value.strip()
    try:
        seconds = float(normalized)
    except ValueError:
        return False
    return isfinite(seconds) and seconds > 0


def normalize_script(script: dict) -> dict:
    """Return a copy with sorted order fields and aligned row cells."""
    next_script = deepcopy(script)
    columns = sorted(next_script.get("columns", []), key=lambda item: item.get("order", 0))
    for index, column in enumerate(columns):
        column["order"] = index
    next_script["columns"] = columns

    column_ids = [column["column_id"] for column in columns]
    duration_column_id = next(
        (column["column_id"] for column in columns if column.get("type") == "duration"),
        None,
    )
    feedback_column_ids = {
        column["column_id"] for column in columns if column.get("key") == BRAND_FEEDBACK_COLUMN_KEY
    }
    rows = sorted(next_script.get("rows", []), key=lambda item: item.get("order", 0))
    for index, row in enumerate(rows):
        row["order"] = index
        cells_by_id = {cell["column_id"]: cell for cell in row.get("cells", []) if "column_id" in cell}
        next_cells = []
        for column_id in column_ids:
            source = cells_by_id.get(column_id, {})
            value = str(source.get("value", ""))
            if column_id == duration_column_id:
                value = _clear_legacy_duration(value)
            cell: dict = {"column_id": column_id, "value": value}
            if column_id in feedback_column_ids and "creator_reply" in source:
                cell["creator_reply"] = str(source.get("creator_reply") or "")
            next_cells.append(cell)
        row["cells"] = next_cells
    next_script["rows"] = rows
    return next_script


def validate_script(script: dict) -> None:
    if not isinstance(script, dict):
        raise ValueError("Script must be an object")

    columns = script.get("columns")
    rows = script.get("rows")
    if not isinstance(columns, list) or not columns:
        raise ValueError("Script must include at least one column")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Script must include at least one row")

    column_ids: set[str] = set()
    duration_column_ids: set[str] = set()
    for index, column in enumerate(columns):
        if not isinstance(column, dict):
            raise ValueError(f"Column at index {index} must be an object")
        column_id = column.get("column_id")
        if not column_id or not isinstance(column_id, str):
            raise ValueError(f"Column at index {index} requires column_id")
        if column_id in column_ids:
            raise ValueError(f"Duplicate column_id: {column_id}")
        column_ids.add(column_id)

        column_type = column.get("type")
        if column_type not in ALLOWED_COLUMN_TYPES:
            raise ValueError(f"Invalid column type: {column_type}")
        if column_type == "duration":
            duration_column_ids.add(column_id)

        key = column.get("key")
        if not key or not isinstance(key, str):
            raise ValueError(f"Column {column_id} requires key")

        label = column.get("label")
        if not label or not isinstance(label, str):
            raise ValueError(f"Column {column_id} requires label")

        if "multiline" not in column or not isinstance(column["multiline"], bool):
            raise ValueError(f"Column {column_id} requires multiline boolean")
        if "order" not in column or not isinstance(column["order"], int):
            raise ValueError(f"Column {column_id} requires numeric order")

    if not duration_column_ids:
        raise ValueError("Script must include a duration column")

    feedback_columns = [column for column in columns if column.get("key") == BRAND_FEEDBACK_COLUMN_KEY]
    if len(feedback_columns) > 1:
        raise ValueError("Script may include at most one feedback column")

    row_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Row at index {index} must be an object")
        row_id = row.get("row_id")
        if not row_id or not isinstance(row_id, str):
            raise ValueError(f"Row at index {index} requires row_id")
        if row_id in row_ids:
            raise ValueError(f"Duplicate row_id: {row_id}")
        row_ids.add(row_id)

        cells = row.get("cells")
        if not isinstance(cells, list):
            raise ValueError(f"Row {row_id} requires cells array")

        seen_cell_columns: set[str] = set()
        for cell in cells:
            if not isinstance(cell, dict):
                raise ValueError(f"Row {row_id} has invalid cell")
            cell_column_id = cell.get("column_id")
            if cell_column_id not in column_ids:
                raise ValueError(f"Row {row_id} references unknown column_id {cell_column_id}")
            if cell_column_id in seen_cell_columns:
                raise ValueError(f"Row {row_id} has duplicate cell for column {cell_column_id}")
            seen_cell_columns.add(cell_column_id)
            if "value" not in cell or not isinstance(cell["value"], str):
                raise ValueError(f"Row {row_id} cell {cell_column_id} requires string value")
            if "creator_reply" in cell and not isinstance(cell["creator_reply"], str):
                raise ValueError(f"Row {row_id} cell {cell_column_id} creator_reply must be a string")
            if cell_column_id in duration_column_ids and cell["value"].strip() and not _valid_duration_value(cell["value"]):
                raise ValueError(f"Row {row_id} duration must be a positive number of seconds")

        if seen_cell_columns != column_ids:
            raise ValueError(f"Row {row_id} must have exactly one cell per column")
