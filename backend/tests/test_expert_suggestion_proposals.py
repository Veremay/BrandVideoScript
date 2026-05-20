import json
import unittest

from app.services.expert_suggestion_proposals import (
    MARKER_END,
    MARKER_START,
    find_marker_start,
    parse_suggestion_items,
    strip_proposal_block,
)


def _wrap(payload: dict) -> str:
    return f"自然语言反馈正文。\n\n{MARKER_START}\n{json.dumps(payload, ensure_ascii=False)}\n{MARKER_END}"


def _allowed_cells(rows: list[tuple[str, str, str]]) -> dict[tuple[str, str], str]:
    return {(row_id, column_id): value for row_id, column_id, value in rows}


def _basic_hunk(*, row_id="row_1", column_id="col_scene", old="原文 A", new="新文 A", reason="替换为具体细节"):
    return {"row_id": row_id, "column_id": column_id, "old": old, "new": new, "reason": reason}


def _basic_suggestion(**overrides):
    base = {
        "title": "强化真实感",
        "direction": "balanced",
        "description": "把抽象表达替换为具体细节。",
        "target_problem": "中段广告感偏强",
        "rationale": "结合 audience_analysis 的 ad_sensitivity_score=4",
        "brand_tradeoff": "卖点露出强度不变",
        "audience_tradeoff": "提升可信度",
        "creator_tradeoff": "需要补充真实细节",
        "risk": "若细节不真实易被识别",
        "explanation_to_brand": "解释话术…",
        "hunks": [_basic_hunk()],
    }
    base.update(overrides)
    return base


class ParseSuggestionItemsTest(unittest.TestCase):
    def test_parses_valid_block(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文 A")])
        text = _wrap({"items": [_basic_suggestion()]})

        items = parse_suggestion_items(text, allowed_cells=allowed)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "强化真实感")
        self.assertEqual(item["direction"], "balanced")
        self.assertEqual(len(item["hunks"]), 1)
        hunk = item["hunks"][0]
        self.assertEqual(hunk["row_id"], "row_1")
        self.assertEqual(hunk["column_id"], "col_scene")
        self.assertEqual(hunk["old"], "原文 A")
        self.assertEqual(hunk["new"], "新文 A")

    def test_drops_hunk_with_old_mismatch(self):
        allowed = _allowed_cells([("row_1", "col_scene", "实际值")])
        text = _wrap({"items": [_basic_suggestion(hunks=[_basic_hunk(old="伪造值")])]})
        items = parse_suggestion_items(text, allowed_cells=allowed)
        self.assertEqual(items, [])

    def test_drops_hunk_targeting_unknown_cell(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文 A")])
        text = _wrap({"items": [_basic_suggestion(hunks=[_basic_hunk(row_id="ghost")])]})
        items = parse_suggestion_items(text, allowed_cells=allowed)
        self.assertEqual(items, [])

    def test_drops_hunk_in_forbidden_column(self):
        allowed = _allowed_cells([("row_1", "col_duration", "0-5")])
        text = _wrap(
            {"items": [_basic_suggestion(hunks=[_basic_hunk(column_id="col_duration", old="0-5", new="0-6")])]}
        )
        items = parse_suggestion_items(
            text,
            allowed_cells=allowed,
            forbidden_columns={"col_duration"},
        )
        self.assertEqual(items, [])

    def test_drops_hunk_when_new_equals_old(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文")])
        text = _wrap({"items": [_basic_suggestion(hunks=[_basic_hunk(old="原文", new="原文")])]})
        items = parse_suggestion_items(text, allowed_cells=allowed)
        self.assertEqual(items, [])

    def test_caps_items_and_hunks(self):
        allowed = _allowed_cells(
            [("row_1", "col_scene", "原文 A"), ("row_2", "col_scene", "原文 B"), ("row_3", "col_scene", "原文 C")]
        )
        suggestions = []
        for i in range(5):
            row = f"row_{(i % 3) + 1}"
            current = {"row_1": "原文 A", "row_2": "原文 B", "row_3": "原文 C"}[row]
            suggestions.append(
                _basic_suggestion(
                    title=f"方案{i}",
                    hunks=[
                        _basic_hunk(row_id=row, old=current, new=f"新文{i}"),
                    ],
                )
            )
        text = _wrap({"items": suggestions})
        items = parse_suggestion_items(text, allowed_cells=allowed)
        self.assertEqual(len(items), 3)

    def test_caps_hunks_per_item(self):
        allowed = _allowed_cells(
            [(f"row_{i}", "col_scene", f"原文 {i}") for i in range(1, 9)]
        )
        hunks = [
            _basic_hunk(row_id=f"row_{i}", old=f"原文 {i}", new=f"新 {i}") for i in range(1, 9)
        ]
        text = _wrap({"items": [_basic_suggestion(hunks=hunks)]})
        items = parse_suggestion_items(text, allowed_cells=allowed)
        self.assertEqual(len(items), 1)
        self.assertLessEqual(len(items[0]["hunks"]), 6)

    def test_deduplicates_hunks_on_same_cell(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文 A")])
        text = _wrap(
            {
                "items": [
                    _basic_suggestion(
                        hunks=[
                            _basic_hunk(new="一版新"),
                            _basic_hunk(new="二版新"),
                        ]
                    )
                ]
            }
        )
        # parser itself does not dedupe within a single item; dedupe happens at stream layer.
        items = parse_suggestion_items(text, allowed_cells=allowed)
        self.assertEqual(len(items[0]["hunks"]), 2)

    def test_falls_back_to_custom_direction(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文 A")])
        text = _wrap({"items": [_basic_suggestion(direction="random_value")]})
        items = parse_suggestion_items(text, allowed_cells=allowed)
        self.assertEqual(items[0]["direction"], "custom")

    def test_ignores_block_without_items_list(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文 A")])
        text = f"{MARKER_START}\n{{\"foo\":1}}\n{MARKER_END}"
        items = parse_suggestion_items(text, allowed_cells=allowed)
        self.assertEqual(items, [])

    def test_tolerant_to_typo_closing_marker(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文 A")])
        # Singular `expert_suggestion` open, plural `expert_suggestions` close, missing `s`.
        raw = (
            "<expert_suggestion>\n"
            + json.dumps({"items": [_basic_suggestion()]}, ensure_ascii=False)
            + "\n</expert_suggestions>"
        )
        items = parse_suggestion_items(raw, allowed_cells=allowed)
        self.assertEqual(len(items), 1)
        self.assertEqual(find_marker_start(raw), 0)

    def test_tolerant_to_missing_closing_marker(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文 A")])
        raw = (
            "<expert_suggestions>\n"
            + json.dumps({"items": [_basic_suggestion()]}, ensure_ascii=False)
            + "\n"
        )
        items = parse_suggestion_items(raw, allowed_cells=allowed)
        self.assertEqual(len(items), 1)

    def test_strip_proposal_block_removes_marker_section(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文 A")])
        text = "正文" + _wrap({"items": [_basic_suggestion()]})
        cleaned = strip_proposal_block(text)
        self.assertNotIn("expert_suggestions", cleaned)
        self.assertIn("正文", cleaned)
        # parsing should still succeed against original text
        self.assertEqual(len(parse_suggestion_items(text, allowed_cells=allowed)), 1)

    def test_handles_markdown_fence(self):
        allowed = _allowed_cells([("row_1", "col_scene", "原文 A")])
        body = json.dumps({"items": [_basic_suggestion()]}, ensure_ascii=False)
        raw = f"<expert_suggestions>\n```json\n{body}\n```\n</expert_suggestions>"
        items = parse_suggestion_items(raw, allowed_cells=allowed)
        self.assertEqual(len(items), 1)


if __name__ == "__main__":
    unittest.main()
