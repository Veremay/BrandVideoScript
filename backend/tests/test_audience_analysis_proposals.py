import unittest

from app.services.audience_analysis_proposals import (
    find_marker_start,
    parse_analysis_payload,
    strip_proposal_block,
)


SAMPLE = '''以 年轻职场人 的视角，我对这段脚本的整体感受：
节奏偏快，第 2 段广告感稍重。

<audience_analysis>
{
  "summary":"中段广告感偏强，但通勤场景可信",
  "naturalness_score":3,
  "credibility_score":4,
  "ad_sensitivity_score":4,
  "key_risks":["品牌口播过早","缺少使用细节"],
  "liked_parts":[{"row_id":"row_1","reason":"通勤场景具体可信"}],
  "rejected_parts":[{"row_id":"row_2","reason":"转折生硬"}],
  "suggestions":["把形容词替换为具体数字"]
}
</audience_analysis>'''


class AudienceAnalysisProposalTest(unittest.TestCase):
    def test_parse_returns_validated_payload(self):
        payload = parse_analysis_payload(SAMPLE, allowed_row_ids={"row_1", "row_2"})
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["naturalness_score"], 3)
        self.assertEqual(payload["credibility_score"], 4)
        self.assertEqual(payload["ad_sensitivity_score"], 4)
        self.assertEqual(payload["liked_parts"][0]["row_id"], "row_1")
        self.assertEqual(payload["rejected_parts"][0]["row_id"], "row_2")
        self.assertIn("品牌口播过早", payload["key_risks"])

    def test_parse_drops_rows_not_in_allowlist(self):
        text = (
            "<audience_analysis>"
            '{"summary":"s","naturalness_score":3,'
            '"liked_parts":[{"row_id":"row_known","reason":"ok"},{"row_id":"row_fake","reason":"bad"}],'
            '"rejected_parts":[]}'
            "</audience_analysis>"
        )
        payload = parse_analysis_payload(text, allowed_row_ids={"row_known"})
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual([part["row_id"] for part in payload["liked_parts"]], ["row_known"])

    def test_parse_returns_none_without_marker(self):
        self.assertIsNone(parse_analysis_payload("plain text", allowed_row_ids=set()))

    def test_parse_drops_invalid_scores(self):
        text = (
            "<audience_analysis>"
            '{"summary":"s","naturalness_score":10,"credibility_score":-1,'
            '"ad_sensitivity_score":"3","suggestions":["s1"]}'
            "</audience_analysis>"
        )
        payload = parse_analysis_payload(text, allowed_row_ids=set())
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertIsNone(payload["naturalness_score"])
        self.assertIsNone(payload["credibility_score"])
        self.assertEqual(payload["ad_sensitivity_score"], 3)
        self.assertEqual(payload["suggestions"], ["s1"])

    def test_parse_returns_none_when_payload_is_empty(self):
        text = "<audience_analysis>{}</audience_analysis>"
        self.assertIsNone(parse_analysis_payload(text, allowed_row_ids=set()))

    def test_parser_tolerates_plural_close_tag(self):
        text = (
            "<audience_analysis>"
            '{"summary":"s","naturalness_score":2}'
            "</audience_analyses>"
        )
        payload = parse_analysis_payload(text, allowed_row_ids=set())
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["naturalness_score"], 2)

    def test_parser_handles_missing_close_tag(self):
        text = (
            "正文...\n\n<audience_analysis>\n"
            '{"summary":"s","naturalness_score":3}'
        )
        payload = parse_analysis_payload(text, allowed_row_ids=set())
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["naturalness_score"], 3)

    def test_strip_removes_marker_block(self):
        cleaned = strip_proposal_block(SAMPLE)
        self.assertIn("节奏偏快", cleaned)
        self.assertNotIn("audience_analysis", cleaned)
        self.assertNotIn("naturalness_score", cleaned)

    def test_strip_handles_typo_close_tag(self):
        text = (
            "正文\n\n<audience_analysis>"
            '{"summary":"s"}'
            "</audience_analyses>"
        )
        cleaned = strip_proposal_block(text)
        self.assertIn("正文", cleaned)
        self.assertNotIn("audience_analysis", cleaned)
        self.assertNotIn("audience_analyses", cleaned)

    def test_find_marker_start_returns_minus_one_when_no_marker(self):
        self.assertEqual(find_marker_start("nothing here"), -1)


if __name__ == "__main__":
    unittest.main()
