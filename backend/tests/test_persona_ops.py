import unittest

from app.repositories.projects import (
    build_audience_analysis,
    build_persona,
    remove_persona_from_list,
    update_persona_in_list,
)


class PersonaBuilderTest(unittest.TestCase):
    def test_build_persona_sets_defaults_and_validates(self):
        persona = build_persona(name=" 年轻职场人 ", trust_trigger=["真实场景", "具体细节"])
        self.assertTrue(persona["persona_id"].startswith("persona_"))
        self.assertEqual(persona["name"], "年轻职场人")
        self.assertEqual(persona["ad_sensitivity"], "medium")
        self.assertEqual(persona["data_source"], "manual")
        self.assertEqual(persona["trust_trigger"], ["真实场景", "具体细节"])
        self.assertEqual(persona["reject_trigger"], [])
        self.assertIsNotNone(persona["created_at"])
        self.assertIsNotNone(persona["updated_at"])

    def test_build_persona_normalizes_comma_separated_triggers(self):
        persona = build_persona(
            name="家庭主妇",
            trust_trigger="柔光, 慢节奏, 真实家居场景",
            reject_trigger="夸张转场,生硬独白",
        )
        self.assertEqual(persona["trust_trigger"], ["柔光", "慢节奏", "真实家居场景"])
        self.assertEqual(persona["reject_trigger"], ["夸张转场", "生硬独白"])

    def test_build_persona_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            build_persona(name="   ")

    def test_build_persona_rejects_invalid_ad_sensitivity(self):
        with self.assertRaises(ValueError):
            build_persona(name="x", ad_sensitivity="invalid")

    def test_update_persona_in_list_changes_only_supplied_fields(self):
        original = build_persona(name="年轻职场人", preferences="效率工具")
        updated = update_persona_in_list(
            [original],
            original["persona_id"],
            {"preferences": "效率工具 + 健康饮食", "ad_sensitivity": "high"},
        )
        self.assertEqual(updated[0]["preferences"], "效率工具 + 健康饮食")
        self.assertEqual(updated[0]["ad_sensitivity"], "high")
        self.assertEqual(updated[0]["name"], "年轻职场人")
        self.assertNotEqual(updated[0]["updated_at"], original["updated_at"])

    def test_update_persona_rejects_blank_name(self):
        original = build_persona(name="年轻职场人")
        with self.assertRaises(ValueError):
            update_persona_in_list([original], original["persona_id"], {"name": "   "})

    def test_update_persona_raises_when_not_found(self):
        with self.assertRaises(ValueError):
            update_persona_in_list([], "persona_missing", {"name": "x"})

    def test_remove_persona_drops_matching_entry(self):
        a = build_persona(name="A")
        b = build_persona(name="B")
        kept = remove_persona_from_list([a, b], a["persona_id"])
        self.assertEqual([p["persona_id"] for p in kept], [b["persona_id"]])

    def test_remove_persona_raises_when_not_found(self):
        a = build_persona(name="A")
        with self.assertRaises(ValueError):
            remove_persona_from_list([a], "persona_missing")


class AudienceAnalysisBuilderTest(unittest.TestCase):
    def test_build_audience_analysis_serializes_payload(self):
        analysis = build_audience_analysis(
            persona_id="persona_1",
            persona_name="年轻职场人",
            summary="整体可信度可接受",
            naturalness_score=3,
            credibility_score=4,
            ad_sensitivity_score=4,
            key_risks=["品牌口播过早"],
            liked_parts=[{"row_id": "row_1", "reason": "通勤场景具体"}],
            rejected_parts=[{"row_id": "row_2", "reason": "转折生硬"}],
            suggestions=["用数字描述替换形容词"],
        )
        self.assertTrue(analysis["analysis_id"].startswith("analysis_"))
        self.assertEqual(analysis["persona_id"], "persona_1")
        self.assertEqual(analysis["naturalness_score"], 3)
        self.assertEqual(analysis["liked_parts"][0]["row_id"], "row_1")
        self.assertIsNotNone(analysis["updated_at"])


if __name__ == "__main__":
    unittest.main()
