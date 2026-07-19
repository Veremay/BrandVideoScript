import unittest

from app.models.script_ops import (
    add_column,
    add_row,
    delete_column,
    delete_row,
    detect_duration_overlaps,
    duration_errors,
    parse_duration_seconds,
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
                    {"column_id": "col_duration", "value": "5"},
                    {"column_id": "col_scene", "value": "Open"},
                ],
            },
            {
                "row_id": "row_b",
                "order": 1,
                "cells": [
                    {"column_id": "col_duration", "value": "5"},
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
        self.assertEqual(script["rows"][0]["cells"], [{"column_id": "col_duration", "value": "5"}])

        with self.assertRaises(ValueError):
            delete_column(script, "col_duration")

    def test_rename_column_updates_label_only(self):
        script = rename_column(sample_script(), "col_scene", "Frame")

        self.assertEqual(script["columns"][1]["label"], "Frame")
        self.assertEqual(script["columns"][1]["key"], "scene")

    def test_automatic_duration_ranges_do_not_overlap(self):
        overlaps = detect_duration_overlaps(sample_script())

        self.assertEqual(overlaps, [])

    def test_duration_seconds_accepts_numbers_only(self):
        self.assertEqual(parse_duration_seconds("5"), 5)
        self.assertEqual(parse_duration_seconds("2.5"), 2.5)
        self.assertIsNone(parse_duration_seconds("10-15"))
        self.assertIsNone(parse_duration_seconds("0"))
        self.assertIsNone(parse_duration_seconds("five"))

    def test_duration_errors_requires_positive_seconds(self):
        script = sample_script()
        script["rows"][0]["cells"][0]["value"] = "5"
        script["rows"][1]["cells"][0]["value"] = "oops"

        self.assertEqual(
            duration_errors(script),
            [{"row_id": "row_b", "message": "Duration must be a positive number of seconds, for example 5 or 2.5"}],
        )

    def test_update_cell_rejects_brand_feedback_column(self):
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
            from app.models.script_ops import update_cell

            update_cell(script, "row_a", "col_feedback", "新反馈")

    def test_update_brand_feedback_cell_allows_feedback_column_only(self):
        from app.models.script_ops import update_brand_feedback_cell, update_cell

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
            row["cells"].append({"column_id": "col_feedback", "value": ""})

        updated = update_brand_feedback_cell(script, "row_a", "col_feedback", "Looks good")
        feedback_value = next(
            cell["value"]
            for row in updated["rows"]
            if row["row_id"] == "row_a"
            for cell in row["cells"]
            if cell["column_id"] == "col_feedback"
        )
        self.assertEqual(feedback_value, "Looks good")

        with self.assertRaises(ValueError):
            update_brand_feedback_cell(script, "row_a", "col_scene", "Blocked")

        with self.assertRaises(ValueError):
            update_cell(script, "row_a", "col_feedback", "Blocked")

    def test_preserve_brand_feedback_cells_keeps_existing_feedback_on_creator_save(self):
        from copy import deepcopy

        from app.models.script_ops import preserve_brand_feedback_cells

        existing = sample_script()
        existing["columns"].append(
            {
                "column_id": "col_feedback",
                "key": "feedback",
                "label": "品牌反馈",
                "type": "textarea",
                "multiline": True,
                "order": 2,
            }
        )
        for row in existing["rows"]:
            row["cells"].append({"column_id": "col_feedback", "value": "Brand note"})

        incoming = deepcopy(existing)
        incoming["rows"][0]["cells"][1]["value"] = "Updated scene"
        for row in incoming["rows"]:
            for cell in row["cells"]:
                if cell["column_id"] == "col_feedback":
                    cell["value"] = "Attempt overwrite"

        preserved = preserve_brand_feedback_cells(incoming, existing)
        feedback_value = next(
            cell["value"]
            for row in preserved["rows"]
            if row["row_id"] == "row_a"
            for cell in row["cells"]
            if cell["column_id"] == "col_feedback"
        )
        self.assertEqual(feedback_value, "Brand note")

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
