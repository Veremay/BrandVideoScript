"""Tests for mutation audit slice helpers."""

from app.services.audit_log import (
    hunk_slice,
    negotiation_preparation_slice,
    node_slice,
    scheme_slice,
    script_slice,
)


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
        "conflict_tags": ["A"],
    }
    sliced = node_slice(node)
    assert sliced is not None
    assert sliced["title"] == "品牌应更突出产品卖点"
    assert sliced["content"] == "建议在第二段加入核心卖点对比"
    assert sliced["conflict_tags"] == ["A"]


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


def test_negotiation_preparation_slice_includes_dispute_text():
    prep = {
        "prep_id": "prep_1",
        "title": "协商沟通方案",
        "design_intent": "兼顾品牌露出与叙事流畅",
        "open_disputes": [
            {
                "issue_node_id": "node_issue_1",
                "brand_feedback": "第二段产品名露出不够",
                "reply": "我们会在口播中补上品牌名",
                "fallback": "可增加字幕露出",
                "talking_points": ["保持节奏", "不牺牲故事线"],
            }
        ],
        "recommended_communication_order": ["node_issue_1"],
        "status": "draft",
    }
    sliced = negotiation_preparation_slice(prep)
    assert sliced is not None
    assert sliced["design_intent"] == "兼顾品牌露出与叙事流畅"
    assert sliced["open_disputes"][0]["brand_feedback"] == "第二段产品名露出不够"
    assert sliced["open_disputes"][0]["reply"] == "我们会在口播中补上品牌名"


def test_scheme_slice_includes_hunk_content():
    scheme = {
        "scheme_id": "scheme_1",
        "title": "强化产品卖点",
        "direction": "brand_leaning",
        "changes_summary": "在第二段加入卖点对比",
        "hunks": [
            {
                "hunk_id": "hunk_1",
                "row_id": "row_1",
                "column_id": "col_scene",
                "removed": "旧画面",
                "added": "新画面：产品特写",
                "decision": "pending",
            }
        ],
        "status": "draft",
    }
    sliced = scheme_slice(scheme)
    assert sliced is not None
    assert sliced["changes_summary"] == "在第二段加入卖点对比"
    assert sliced["hunks"][0]["added"] == "新画面：产品特写"
