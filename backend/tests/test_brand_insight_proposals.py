import unittest

from app.services.brand_insight_proposals import (
    parse_proposal_items,
    strip_proposal_block,
)


SAMPLE_PAYLOAD = '''关于这段脚本我的反馈如下：
1. 镜头切换有点快...

<brand_insight_proposals>
{"items":[
  {
    "category":"implicit_requirement",
    "title":"保持留白感",
    "content":"画面节奏不宜过快，每个产品镜头给足停留时间。",
    "reason":"品牌强调东方留白调性。",
    "confidence":"medium",
    "evidence":[{"source_type":"brand_wiki","quote":"留白感"}]
  },
  {
    "category":"explicit_requirement",
    "title":"必须出现产品全貌",
    "content":"成片至少有一个 3 秒以上的产品全貌镜头。",
    "reason":"Brief 明确要求。",
    "confidence":"high",
    "evidence":[{"source_type":"brief","quote":"产品需要完整露出"}]
  }
]}
</brand_insight_proposals>'''


class BrandInsightProposalParserTest(unittest.TestCase):
    def test_parse_returns_validated_items(self):
        items = parse_proposal_items(SAMPLE_PAYLOAD)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["category"], "implicit_requirement")
        self.assertEqual(items[1]["confidence"], "high")
        self.assertEqual(items[1]["evidence"][0]["source_type"], "brief")

    def test_parse_returns_empty_when_no_marker(self):
        self.assertEqual(parse_proposal_items("plain assistant text"), [])

    def test_parse_drops_items_missing_title_or_content(self):
        bad = "<brand_insight_proposals>{\"items\":[{\"category\":\"explicit_requirement\"}]}</brand_insight_proposals>"
        self.assertEqual(parse_proposal_items(bad), [])

    def test_parse_drops_items_with_invalid_category(self):
        bad = (
            "<brand_insight_proposals>{\"items\":[{"
            "\"category\":\"random\",\"title\":\"T\",\"content\":\"C\"}]}"
            "</brand_insight_proposals>"
        )
        self.assertEqual(parse_proposal_items(bad), [])

    def test_parse_handles_json_fence_inside_marker(self):
        wrapped = (
            "<brand_insight_proposals>\n```json\n"
            '{"items":[{"category":"brand_feedback","title":"T","content":"C","confidence":"low"}]}'
            "\n```\n</brand_insight_proposals>"
        )
        items = parse_proposal_items(wrapped)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "brand_feedback")

    def test_strip_proposal_block_removes_marker_and_trailing_whitespace(self):
        cleaned = strip_proposal_block(SAMPLE_PAYLOAD)
        self.assertIn("镜头切换有点快", cleaned)
        self.assertNotIn("brand_insight_proposals", cleaned)
        self.assertNotIn("implicit_requirement", cleaned)
        self.assertFalse(cleaned.endswith("\n"))

    def test_parser_tolerates_plural_typo_in_closing_tag(self):
        text = (
            "正文反馈...\n\n<brand_insight_proposals>\n"
            '{"items":[{"category":"implicit_requirement","title":"T","content":"C",'
            '"confidence":"medium","evidence":[{"source_type":"brief","quote":"q"}]}]}'
            "\n</brand_insights_proposals>"
        )
        items = parse_proposal_items(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "T")

    def test_stripper_tolerates_plural_typo_in_closing_tag(self):
        text = (
            "正文反馈...\n\n<brand_insight_proposals>\n"
            '{"items":[{"category":"implicit_requirement","title":"T","content":"C"}]}'
            "\n</brand_insights_proposals>"
        )
        cleaned = strip_proposal_block(text)
        self.assertIn("正文反馈", cleaned)
        self.assertNotIn("brand_insight_proposals", cleaned)
        self.assertNotIn("brand_insights_proposals", cleaned)
        self.assertNotIn("implicit_requirement", cleaned)

    def test_stripper_handles_missing_closing_tag_by_truncating_to_end(self):
        text = (
            "正文反馈...\n\n<brand_insight_proposals>\n"
            '{"items":[{"category":"implicit_requirement","title":"T","content":"C"}]}'
        )
        cleaned = strip_proposal_block(text)
        self.assertEqual(cleaned, "正文反馈...")

    def test_parser_handles_plural_opening_tag(self):
        text = (
            "<brand_insights_proposals>"
            '{"items":[{"category":"brand_feedback","title":"T","content":"C"}]}'
            "</brand_insights_proposals>"
        )
        items = parse_proposal_items(text)
        self.assertEqual(len(items), 1)


if __name__ == "__main__":
    unittest.main()
