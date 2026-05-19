import json
import unittest

from app.services import brand_brief_pipeline as pipeline


class BrandBriefPipelineTest(unittest.TestCase):
    def test_parse_insights_payload_accepts_raw_json(self):
        raw = json.dumps(
            {
                "insights": [
                    {
                        "category": "explicit_requirement",
                        "title": "T1",
                        "content": "C1",
                        "reason": "R1",
                        "confidence": "high",
                        "evidence": [{"source_type": "brief", "quote": "q1"}],
                    }
                ]
            }
        )
        items = pipeline._parse_insights_payload(raw)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "explicit_requirement")
        self.assertEqual(items[0]["title"], "T1")

    def test_parse_insights_payload_strips_markdown_fence(self):
        raw = '```json\n{"insights":[]}\n```'
        items = pipeline._parse_insights_payload(raw)
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
