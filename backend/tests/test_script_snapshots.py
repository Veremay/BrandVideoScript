import unittest
from copy import deepcopy

from app.repositories.script_snapshots import (
    SNAPSHOT_REASONS,
    build_snapshot,
    serialize_snapshot_summary,
)


def _sample_script() -> dict:
    return {
        "columns": [{"column_id": "col_scene", "label": "画面", "type": "textarea", "multiline": True, "order": 0}],
        "rows": [{"row_id": "row_1", "order": 0, "cells": [{"column_id": "col_scene", "value": "..."}]}],
        "updated_at": "2026-05-19T00:00:00",
    }


class SnapshotBuilderTest(unittest.TestCase):
    def test_build_snapshot_includes_all_metadata(self):
        snapshot = build_snapshot(
            project_id="p1",
            user_id="u1",
            reason="before_expert_apply",
            script=_sample_script(),
            suggestion_id="suggestion_1",
            applied_hunk_ids=["hunk_a"],
        )
        self.assertTrue(snapshot["_id"].startswith("snapshot_"))
        self.assertEqual(snapshot["project_id"], "p1")
        self.assertEqual(snapshot["user_id"], "u1")
        self.assertEqual(snapshot["reason"], "before_expert_apply")
        self.assertEqual(snapshot["suggestion_id"], "suggestion_1")
        self.assertEqual(snapshot["applied_hunk_ids"], ["hunk_a"])
        self.assertEqual(snapshot["script"]["rows"][0]["row_id"], "row_1")
        self.assertIn(snapshot["reason"], SNAPSHOT_REASONS)

    def test_build_snapshot_deep_copies_script(self):
        script = _sample_script()
        snapshot = build_snapshot(
            project_id="p1",
            user_id="u1",
            reason="manual_save",
            script=script,
        )
        script["rows"][0]["cells"][0]["value"] = "mutated"
        self.assertNotEqual(snapshot["script"]["rows"][0]["cells"][0]["value"], "mutated")

    def test_build_snapshot_rejects_invalid_reason(self):
        with self.assertRaises(ValueError):
            build_snapshot(
                project_id="p1",
                user_id="u1",
                reason="invalid",
                script=_sample_script(),
            )

    def test_serialize_summary_drops_script(self):
        document = build_snapshot(
            project_id="p1",
            user_id="u1",
            reason="manual_save",
            script=_sample_script(),
        )
        summary = serialize_snapshot_summary(document)
        self.assertNotIn("script", summary)
        self.assertEqual(summary["reason"], "manual_save")
        self.assertEqual(summary["_id"], document["_id"])


if __name__ == "__main__":
    unittest.main()
