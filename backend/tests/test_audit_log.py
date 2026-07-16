"""Tests for mutation audit slice helpers."""

from app.services.audit_log import hunk_slice, node_slice, script_slice


def test_script_slice_includes_cell_values():
    script = {
        "settings": {"mode": "full"},
        "columns": [{"column_id": "col_scene", "key": "scene", "label": "画面", "type": "textarea", "order": 0}],
        "rows": [
            {
                "row_id": "row_1",
                "order": 0,
                "cells": [{"column_id": "col_scene", "value": "开场镜头"}],
            }
        ],
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    sliced = script_slice(script)
    assert sliced is not None
    assert sliced["rows"][0]["cells"][0]["value"] == "开场镜头"


def test_node_slice_includes_content():
    node = {
        "node_id": "node_1",
        "node_type": "position",
        "title": "品牌应更突出产品卖点",
        "content": "建议在第二段加入核心卖点对比",
        "status": "open",
    }
    sliced = node_slice(node)
    assert sliced is not None
    assert sliced["title"] == "品牌应更突出产品卖点"
    assert sliced["content"] == "建议在第二段加入核心卖点对比"


def test_hunk_slice_includes_removed_and_added():
    hunk = {
        "hunk_id": "hunk_1",
        "row_id": "row_1",
        "column_id": "col_scene",
        "context": "调整画面描述",
        "removed": "旧文案",
        "added": "新文案",
        "decision": "accepted",
    }
    sliced = hunk_slice(hunk)
    assert sliced is not None
    assert sliced["removed"] == "旧文案"
    assert sliced["added"] == "新文案"
