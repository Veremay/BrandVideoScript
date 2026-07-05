import unittest

from app.models.choice_history import (
    format_choice_history_for_prompt,
    record_considered_position,
    record_scheme_position_usage,
)
from app.repositories.projects import serialize_project


class ChoiceHistoryTest(unittest.TestCase):
    def test_serialize_project_defaults_choice_history_for_existing_projects(self) -> None:
        project = serialize_project({"_id": "project_1"})

        self.assertEqual(project["choice_history"], {"adopted_positions": [], "scheme_position_links": []})

    def test_record_considered_position_deduplicates_and_updates_last_seen(self) -> None:
        node = {
            "node_id": "pos_1",
            "title": "Keep the natural opening",
            "content": "The slower opening improves trust.",
            "source_type": "audience_simulation",
            "source_perspective": "audience",
            "lifecycle": "active",
        }
        history = record_considered_position({}, node, now="2026-07-05T10:00:00")
        history = record_considered_position(history, node, now="2026-07-05T11:00:00")

        positions = history["adopted_positions"]
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["position_id"], "pos_1")
        self.assertEqual(positions[0]["first_considered_at"], "2026-07-05T10:00:00")
        self.assertEqual(positions[0]["last_considered_at"], "2026-07-05T11:00:00")
        self.assertEqual(positions[0]["title_snapshot"], "Keep the natural opening")

    def test_record_scheme_position_usage_preserves_scheme_position_links(self) -> None:
        history = record_scheme_position_usage(
            {},
            {
                "scheme_id": "scheme_1",
                "title": "Balanced revision",
                "direction": "balanced",
                "target_position_ids": ["pos_1", "pos_2"],
                "created_at": "2026-07-05T12:00:00",
            },
            nodes_by_id={
                "pos_1": {"node_id": "pos_1", "title": "Audience trust", "content": "Keep it natural."},
                "pos_2": {"node_id": "pos_2", "title": "Brand visibility", "content": "Show the product."},
            },
            now="2026-07-05T12:00:00",
        )

        self.assertEqual(history["scheme_position_links"][0]["scheme_id"], "scheme_1")
        self.assertEqual(history["scheme_position_links"][0]["target_position_ids"], ["pos_1", "pos_2"])
        positions = {item["position_id"]: item for item in history["adopted_positions"]}
        self.assertEqual(positions["pos_1"]["last_used_for_scheme_at"], "2026-07-05T12:00:00")
        self.assertEqual(positions["pos_1"]["used_scheme_ids"], ["scheme_1"])
        self.assertEqual(positions["pos_2"]["title_snapshot"], "Brand visibility")

    def test_format_choice_history_for_prompt_mentions_positions_and_schemes(self) -> None:
        history = {
            "adopted_positions": [
                {
                    "position_id": "pos_1",
                    "title_snapshot": "Audience trust",
                    "content_snapshot": "Keep the opening natural.",
                    "used_scheme_ids": ["scheme_1"],
                    "last_used_for_scheme_at": "2026-07-05T12:00:00",
                }
            ],
            "scheme_position_links": [
                {
                    "scheme_id": "scheme_1",
                    "title": "Balanced revision",
                    "direction": "balanced",
                    "target_position_ids": ["pos_1"],
                }
            ],
        }

        prompt = format_choice_history_for_prompt(history)

        self.assertIn("Audience trust", prompt)
        self.assertIn("scheme_1", prompt)
        self.assertIn("Balanced revision", prompt)


if __name__ == "__main__":
    unittest.main()
