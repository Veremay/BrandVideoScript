import unittest

from app.models.modification_scheme_ops import (
    apply_hunk_to_script,
    get_cell_value,
    normalize_scheme,
    reconcile_hunk_for_apply,
    resolve_hunk_identifiers,
    validate_hunk_apply,
)
from app.models.script import default_script
from app.models.script_ops import update_cell


class ModificationSchemeOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = default_script()
        self.row_id = self.script["rows"][0]["row_id"]
        scene_col = next(column for column in self.script["columns"] if column["key"] == "scene")
        self.column_id = scene_col["column_id"]
        self.script = update_cell(self.script, self.row_id, self.column_id, "开场镜头")

    def test_validate_hunk_apply_rejects_stale_cell(self) -> None:
        hunk = {
            "hunk_id": "hunk_1",
            "row_id": self.row_id,
            "column_id": self.column_id,
            "removed": "旧文本",
            "added": "新文本",
        }
        with self.assertRaises(ValueError):
            validate_hunk_apply(self.script, hunk)

    def test_apply_hunk_updates_cell(self) -> None:
        current = get_cell_value(self.script, self.row_id, self.column_id)
        hunk = {
            "hunk_id": "hunk_1",
            "row_id": self.row_id,
            "column_id": self.column_id,
            "removed": current,
            "added": "更新后的开场",
        }
        next_script = apply_hunk_to_script(self.script, hunk)
        self.assertEqual(get_cell_value(next_script, self.row_id, self.column_id), "更新后的开场")

    def test_resolve_hunk_identifiers_maps_column_key_and_removed_text(self) -> None:
        resolved = resolve_hunk_identifiers(
            self.script,
            {
                "row_id": "ignored",
                "column_id": "scene",
                "removed": "开场镜头",
                "added": "更新后的开场",
            },
        )
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved["row_id"], self.row_id)
        self.assertEqual(resolved["column_id"], self.column_id)
        self.assertEqual(resolved["removed"], "开场镜头")

    def test_normalize_scheme_anchors_removed_to_live_cell(self) -> None:
        scheme = normalize_scheme(
            {
                "title": "平衡方案",
                "direction": "balanced",
                "target_issue_ids": ["node_1"],
                "hunks": [
                    {
                        "row_id": self.row_id,
                        "column_id": self.column_id,
                        "removed": "LLM paraphrased opening",
                        "added": "平衡版开场",
                    }
                ],
            },
            project_id="project_1",
            script_version_id="ver_1",
            script=self.script,
        )
        self.assertEqual(scheme["hunks"][0]["removed"], "开场镜头")
        self.assertEqual(scheme["hunks"][0]["added"], "平衡版开场")

    def test_reconcile_hunk_rebases_removed_onto_live_cell(self) -> None:
        hunk = {
            "hunk_id": "hunk_1",
            "row_id": self.row_id,
            "column_id": self.column_id,
            "removed": "旧文本",
            "added": "新文本",
        }
        reconciled = reconcile_hunk_for_apply(self.script, hunk)
        self.assertEqual(reconciled["removed"], "开场镜头")
        next_script = apply_hunk_to_script(self.script, reconciled)
        self.assertEqual(get_cell_value(next_script, self.row_id, self.column_id), "新文本")

    def test_reconcile_hunk_treats_already_applied_as_compatible(self) -> None:
        hunk = {
            "hunk_id": "hunk_1",
            "row_id": self.row_id,
            "column_id": self.column_id,
            "removed": "别的原文",
            "added": "开场镜头",
        }
        reconciled = reconcile_hunk_for_apply(self.script, hunk)
        self.assertEqual(reconciled["removed"], "开场镜头")


if __name__ == "__main__":
    unittest.main()
