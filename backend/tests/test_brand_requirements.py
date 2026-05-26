import unittest

from app.repositories.projects import normalize_brand_requirements


class BrandRequirementsTest(unittest.TestCase):
    def test_normalize_skips_empty_text_and_invalid_confidence(self) -> None:
        items = normalize_brand_requirements(
            [
                {"text": "  必须真实通勤  ", "confidence": "high", "id": "r1"},
                {"text": "", "confidence": "high"},
                {"text": "避免硬广", "confidence": "invalid"},
            ]
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["text"], "必须真实通勤")
        self.assertEqual(items[0]["confidence"], "high")
        self.assertEqual(items[1]["confidence"], "medium")


if __name__ == "__main__":
    unittest.main()
