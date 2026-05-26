import unittest

from app.models.modification_scheme_ops import (
    apply_hunk_to_script,
    get_cell_value,
    normalize_scheme,
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

    def test_normalize_scheme_requires_at_least_two_directions_in_mock_flow(self) -> None:
        scheme = normalize_scheme(
            {
                "title": "平衡方案",
                "direction": "balanced",
                "target_issue_ids": ["node_1"],
                "hunks": [
                    {
                        "row_id": self.row_id,
                        "column_id": self.column_id,
                        "removed": "开场镜头",
                        "added": "平衡版开场",
                    }
                ],
            },
            project_id="project_1",
            script_version_id="ver_1",
            script=self.script,
        )
        self.assertEqual(scheme["direction"], "balanced")
        self.assertEqual(len(scheme["hunks"]), 1)
        self.assertEqual(scheme["hunks"][0]["removed"], "开场镜头")


if __name__ == "__main__":
    unittest.main()
