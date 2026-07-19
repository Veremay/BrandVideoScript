from copy import deepcopy
from math import isfinite

from app.models.script import BRAND_FEEDBACK_COLUMN_KEY, new_id


def _sorted_columns(script: dict) -> list[dict]:
    return sorted(script.get("columns", []), key=lambda column: column.get("order", 0))


def _sorted_rows(script: dict) -> list[dict]:
    return sorted(script.get("rows", []), key=lambda row: row.get("order", 0))


def _reorder(items: list[dict]) -> list[dict]:
    for index, item in enumerate(items):
        item["order"] = index
    return items


def _new_cell(column_id: str) -> dict:
    return {"column_id": column_id, "value": ""}


def add_row(script: dict, after_row_id: str | None = None) -> dict:
    next_script = deepcopy(script)
    columns = _sorted_columns(next_script)
    rows = _sorted_rows(next_script)
    new_row = {
        "row_id": new_id("row"),
        "order": 0,
        "cells": [_new_cell(column["column_id"]) for column in columns],
    }

    insert_at = len(rows)
    if after_row_id:
        for index, row in enumerate(rows):
            if row["row_id"] == after_row_id:
                insert_at = index + 1
                break

    rows.insert(insert_at, new_row)
    next_script["rows"] = _reorder(rows)
    return next_script


def delete_row(script: dict, row_id: str) -> dict:
    next_script = deepcopy(script)
    rows = _sorted_rows(next_script)
    if len(rows) <= 1:
        raise ValueError("Cannot delete the last row")

    next_rows = [row for row in rows if row["row_id"] != row_id]
    if len(next_rows) == len(rows):
        raise ValueError("Row not found")

    next_script["rows"] = _reorder(next_rows)
    return next_script


def add_column(
    script: dict,
    *,
    after_column_id: str | None = None,
    label: str,
    column_type: str = "text",
    multiline: bool = False,
) -> dict:
    next_script = deepcopy(script)
    columns = _sorted_columns(next_script)
    column = {
        "column_id": new_id("col"),
        "key": f"custom_{new_id('field')}",
        "label": label,
        "type": column_type,
        "multiline": multiline,
        "order": 0,
    }

    insert_at = len(columns)
    if after_column_id:
        for index, existing in enumerate(columns):
            if existing["column_id"] == after_column_id:
                insert_at = index + 1
                break

    columns.insert(insert_at, column)
    next_script["columns"] = _reorder(columns)

    for row in _sorted_rows(next_script):
        cells_by_id = {cell["column_id"]: cell for cell in row.get("cells", [])}
        row["cells"] = [cells_by_id.get(item["column_id"], _new_cell(item["column_id"])) for item in next_script["columns"]]

    return next_script


def delete_column(script: dict, column_id: str) -> dict:
    next_script = deepcopy(script)
    columns = _sorted_columns(next_script)
    if len(columns) <= 1:
        raise ValueError("Cannot delete the last business column")

    target = next((column for column in columns if column["column_id"] == column_id), None)
    if target is not None and target.get("key") == "duration":
        raise ValueError("Cannot delete the duration column")
    if target is not None and target.get("key") == "feedback":
        raise ValueError("Cannot delete the brand feedback column")

    next_columns = [column for column in columns if column["column_id"] != column_id]
    if len(next_columns) == len(columns):
        raise ValueError("Column not found")

    next_script["columns"] = _reorder(next_columns)
    for row in _sorted_rows(next_script):
        row["cells"] = [cell for cell in row.get("cells", []) if cell["column_id"] != column_id]

    return next_script


def rename_column(script: dict, column_id: str, label: str) -> dict:
    next_script = deepcopy(script)
    renamed = False
    for column in next_script.get("columns", []):
        if column["column_id"] == column_id:
            if column.get("key") == "feedback":
                raise ValueError("Cannot rename the brand feedback column")
            column["label"] = label
            renamed = True
            break

    if not renamed:
        raise ValueError("Column not found")

    return next_script


def _feedback_column_id(script: dict) -> str | None:
    for column in script.get("columns", []):
        if column.get("key") == BRAND_FEEDBACK_COLUMN_KEY:
            return column.get("column_id")
    return None


def preserve_brand_feedback_cells(incoming: dict, existing: dict) -> dict:
    """Keep brand feedback values from the database when the creator saves the script."""
    column_id = _feedback_column_id(existing)
    if not column_id:
        return incoming

    existing_by_row: dict[str, str] = {}
    for row in existing.get("rows", []):
        for cell in row.get("cells", []):
            if cell.get("column_id") == column_id:
                existing_by_row[row["row_id"]] = str(cell.get("value", ""))
                break

    next_script = deepcopy(incoming)
    for row in next_script.get("rows", []):
        preserved = existing_by_row.get(row["row_id"])
        if preserved is None:
            continue
        for cell in row.get("cells", []):
            if cell.get("column_id") == column_id:
                cell["value"] = preserved
                break
    return next_script


def update_brand_feedback_cell(script: dict, row_id: str, column_id: str, value: str) -> dict:
    next_script = deepcopy(script)
    target_column = next(
        (column for column in next_script.get("columns", []) if column.get("column_id") == column_id),
        None,
    )
    if target_column is None:
        raise ValueError("Column not found")
    if target_column.get("key") != BRAND_FEEDBACK_COLUMN_KEY:
        raise ValueError("Only the brand feedback column can be edited via share link")

    updated = False
    for row in next_script.get("rows", []):
        if row["row_id"] != row_id:
            continue
        for cell in row.get("cells", []):
            if cell["column_id"] == column_id:
                cell["value"] = value
                updated = True
                break

    if not updated:
        raise ValueError("Cell not found")

    return next_script


def update_cell(script: dict, row_id: str, column_id: str, value: str) -> dict:
    next_script = deepcopy(script)
    target_column = next((column for column in next_script.get("columns", []) if column.get("column_id") == column_id), None)
    if target_column is not None and target_column.get("key") == BRAND_FEEDBACK_COLUMN_KEY:
        raise ValueError("Cannot edit the brand feedback column")

    updated = False
    for row in next_script.get("rows", []):
        if row["row_id"] != row_id:
            continue
        for cell in row.get("cells", []):
            if cell["column_id"] == column_id:
                cell["value"] = value
                updated = True
                break

    if not updated:
        raise ValueError("Cell not found")

    return next_script


def parse_duration(value: str) -> tuple[float, float] | None:
    parts = [part.strip() for part in value.split("-", 1)]
    if len(parts) != 2:
        return None
    try:
        start = float(parts[0])
        end = float(parts[1])
    except ValueError:
        return None
    if start < 0 or end <= start:
        return None
    return start, end


def parse_duration_seconds(value: str) -> float | None:
    """Parse a seconds-only duration."""
    stripped = value.strip()
    if not stripped:
        return None
    try:
        seconds = float(stripped)
    except ValueError:
        return None
    return seconds if isfinite(seconds) and seconds > 0 else None


def duration_errors(script: dict) -> list[dict]:
    duration_column = next((column for column in script.get("columns", []) if column.get("type") == "duration"), None)
    if not duration_column:
        return []

    errors = []
    for row in _sorted_rows(script):
        value = next((cell.get("value", "") for cell in row.get("cells", []) if cell["column_id"] == duration_column["column_id"]), "")
        if value and parse_duration_seconds(value) is None:
            errors.append({"row_id": row["row_id"], "message": "Duration must be a positive number of seconds, for example 5 or 2.5"})
    return errors


def detect_duration_overlaps(script: dict) -> list[dict]:
    duration_column = next((column for column in script.get("columns", []) if column.get("type") == "duration"), None)
    if not duration_column:
        return []

    ranges = []
    for row in _sorted_rows(script):
        value = next((cell.get("value", "") for cell in row.get("cells", []) if cell["column_id"] == duration_column["column_id"]), "")
        parsed = parse_duration(value)
        if parsed:
            ranges.append({"row_id": row["row_id"], "start": parsed[0], "end": parsed[1]})

    overlaps = []
    for index, current in enumerate(ranges):
        for candidate in ranges[index + 1 :]:
            start = max(current["start"], candidate["start"])
            end = min(current["end"], candidate["end"])
            if start < end:
                overlaps.append({"row_ids": [current["row_id"], candidate["row_id"]], "range": f"{start:g}-{end:g}"})
    return overlaps
