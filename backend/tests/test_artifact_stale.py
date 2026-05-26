import unittest

from app.models.artifact_stale import default_stale, is_artifact_stale, mark_script_changed, stale_set_fields


class ArtifactStaleTest(unittest.TestCase):
    def test_default_stale_is_up_to_date(self):
        stale = default_stale()
        self.assertFalse(is_artifact_stale(stale, "rationale_graph"))
        self.assertEqual(stale["modification_schemes"], "up_to_date")

    def test_mark_script_changed_sets_all_artifacts(self):
        updates = stale_set_fields(mark_script_changed())
        self.assertEqual(updates["stale.rationale_graph"], "stale_script_changed")
        self.assertTrue(is_artifact_stale({"rationale_graph": "stale_script_changed"}, "rationale_graph"))


if __name__ == "__main__":
    unittest.main()
