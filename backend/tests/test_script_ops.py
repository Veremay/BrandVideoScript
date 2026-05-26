import unittest

from app.models.script_ops import (
    add_column,
    add_row,
    delete_column,
    delete_row,
    detect_duration_overlaps,
    rename_column,
)


def sample_script():
    return {
        "columns": [
            {"column_id": "col_duration", "key": "duration", "label": "Duration", "type": "duration", "multiline": False, "order": 0},
            {"column_id": "col_scene", "key": "scene", "label": "Scene", "type": "textarea", "multiline": True, "order": 1},
        ],
        "rows": [
            {
                "row_id": "row_a",
                "order": 0,
                "cells": [
                    {"column_id": "col_duration", "value": "0-5"},
                    {"column_id": "col_scene", "value": "Open"},
                ],
            },
            {
                "row_id": "row_b",
                "order": 1,
                "cells": [
                    {"column_id": "col_duration", "value": "4-9"},
                    {"column_id": "col_scene", "value": "Demo"},
                ],
            },
        ],
    }


class ScriptOpsTest(unittest.TestCase):
    def test_add_row_after_target_keeps_cells_aligned_to_columns(self):
        script = add_row(sample_script(), after_row_id="row_a")

        self.assertEqual([row["order"] for row in script["rows"]], [0, 1, 2])
        self.assertEqual(script["rows"][1]["cells"], [
            {"column_id": "col_duration", "value": ""},
            {"column_id": "col_scene", "value": ""},
        ])

    def test_delete_row_rejects_deleting_last_row(self):
        script = sample_script()
        script["rows"] = script["rows"][:1]

        with self.assertRaises(ValueError):
            delete_row(script, "row_a")

    def test_add_column_after_target_adds_empty_cells_to_every_row(self):
        script = add_column(sample_script(), after_column_id="col_duration", label="Shot", column_type="text", multiline=False)

        self.assertEqual([column["order"] for column in script["columns"]], [0, 1, 2])
        self.assertEqual(script["columns"][1]["label"], "Shot")
        for row in script["rows"]:
            self.assertEqual(row["cells"][1]["value"], "")

    def test_delete_column_removes_matching_cells_and_rejects_last_business_column(self):
        script = delete_column(sample_script(), "col_scene")

        self.assertEqual([column["column_id"] for column in script["columns"]], ["col_duration"])
        self.assertEqual(script["rows"][0]["cells"], [{"column_id": "col_duration", "value": "0-5"}])

        with self.assertRaises(ValueError):
            delete_column(script, "col_duration")

    def test_rename_column_updates_label_only(self):
        script = rename_column(sample_script(), "col_scene", "Frame")

        self.assertEqual(script["columns"][1]["label"], "Frame")
        self.assertEqual(script["columns"][1]["key"], "scene")

    def test_detect_duration_overlaps_reports_crossing_ranges(self):
        overlaps = detect_duration_overlaps(sample_script())

        self.assertEqual(overlaps, [{"row_ids": ["row_a", "row_b"], "range": "4-5"}])

    def test_delete_column_rejects_brand_feedback_column(self):
        script = sample_script()
        script["columns"].append(
            {
                "column_id": "col_feedback",
                "key": "feedback",
                "label": "品牌反馈",
                "type": "textarea",
                "multiline": True,
                "order": 2,
            }
        )
        for row in script["rows"]:
            row["cells"].append({"column_id": "col_feedback", "value": "请加强品牌露出"})

        with self.assertRaises(ValueError):
            delete_column(script, "col_feedback")


if __name__ == "__main__":
    unittest.main()
