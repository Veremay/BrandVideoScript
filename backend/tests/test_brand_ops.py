import unittest

from app.repositories.projects import (
    build_brand_insight,
    build_brief,
    remove_brand_insight_from_list,
    update_brand_insight_in_list,
)


class BrandOpsTest(unittest.TestCase):
    def test_build_brief_marks_text_as_parsed_and_summarizes_first_lines(self):
        brief = build_brief(
            filename="launch.md",
            text="Main selling point: quiet motor.\nCreator must show a real commute.\nAvoid hard-sell language.",
        )

        self.assertEqual(brief["filename"], "launch.md")
        self.assertEqual(brief["text"], "Main selling point: quiet motor.\nCreator must show a real commute.\nAvoid hard-sell language.")
        self.assertEqual(brief["parse_status"], "pending")
        self.assertIn("Main selling point", brief["summary"])
        self.assertIsNotNone(brief["uploaded_at"])

    def test_build_brief_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            build_brief(filename="empty.txt", text="   ")

    def test_build_brand_insight_sets_required_metadata_defaults(self):
        insight = build_brand_insight(
            category="explicit_requirement",
            title="Show the product in use",
            content="Include a real daily-use scene.",
            reason="The brief asks for a practical demo.",
            evidence=[{"source_type": "brief", "quote": "daily commute demo"}],
            created_by="user",
        )

        self.assertTrue(insight["insight_id"].startswith("insight_"))
        self.assertEqual(insight["category"], "explicit_requirement")
        self.assertEqual(insight["confidence"], "medium")
        self.assertEqual(insight["status"], "new")
        self.assertEqual(insight["created_by"], "user")
        self.assertEqual(insight["updated_by"], "user")
        self.assertIsNotNone(insight["created_at"])
        self.assertIsNotNone(insight["updated_at"])

    def test_update_brand_insight_changes_only_requested_fields(self):
        original = build_brand_insight(
            category="implicit_requirement",
            title="Keep creator voice",
            content="Avoid copy that sounds like a hard ad.",
            reason="Audience trust matters.",
            evidence=[],
            confidence="low",
            status="pending",
        )

        updated = update_brand_insight_in_list(
            [original],
            original["insight_id"],
            {"content": "Keep the creator's normal phrasing.", "confidence": "high"},
        )

        self.assertEqual(updated[0]["title"], "Keep creator voice")
        self.assertEqual(updated[0]["content"], "Keep the creator's normal phrasing.")
        self.assertEqual(updated[0]["confidence"], "high")
        self.assertEqual(updated[0]["status"], "pending")
        self.assertEqual(updated[0]["updated_by"], "user")
        self.assertNotEqual(updated[0]["updated_at"], original["updated_at"])

    def test_remove_brand_insight_from_list_deletes_matching_item(self):
        first = build_brand_insight(
            category="brand_feedback",
            title="PR feedback",
            content="Mention the launch date.",
            reason="Brand explicitly requested it.",
            evidence=[],
        )
        second = build_brand_insight(
            category="explicit_requirement",
            title="CTA",
            content="Mention where to buy.",
            reason="Brief includes sales CTA.",
            evidence=[],
        )

        updated = remove_brand_insight_from_list([first, second], first["insight_id"])

        self.assertEqual([insight["insight_id"] for insight in updated], [second["insight_id"]])


if __name__ == "__main__":
    unittest.main()
