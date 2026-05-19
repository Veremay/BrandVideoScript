import json
import unittest
from unittest.mock import AsyncMock, patch

from app.services.brand_brief_pipeline import (
    _build_search_queries,
    _extract_brand_name,
    _llm_extract_brand_entity,
    _looks_like_valid_brand,
    _parse_brand_entity_payload,
)


SAMPLE_BRIEF = """### 📌【合作 brief】观夏 × 视频创作者：陶瓷香挂系列推广合作

#### 一、品牌介绍
**观夏 To Summer**，东方植物调香氛品牌。
我们坚持挖掘中国人记忆中的自然香气，以东方植物为灵感，融合全球优质原料与手工技艺，创作有呼吸感、留白感的香气作品。

#### 二、产品介绍：陶瓷香挂
**产品名称**：陶瓷香挂（Scented Ceramic Diffuser）
"""


class BrandSearchQueryTest(unittest.TestCase):
    def test_extract_brand_name_prefers_markdown_bold_brand_x_partner(self):
        name = _extract_brand_name(SAMPLE_BRIEF, filename="观夏brief.md")
        self.assertEqual(name, "观夏")

    def test_extract_brand_name_falls_back_to_cleaned_filename(self):
        name = _extract_brand_name("没有可识别品牌的正文", filename="某品牌-brand-brief.md")
        self.assertEqual(name, "某品牌")

    def test_extract_brand_name_strips_chinese_brief_suffix_from_filename(self):
        name = _extract_brand_name("没有可识别品牌的正文", filename="观夏品牌简报.md")
        self.assertEqual(name, "观夏")

    def test_build_search_queries_includes_brand_and_product_hint(self):
        queries = _build_search_queries("观夏", SAMPLE_BRIEF)
        self.assertGreaterEqual(len(queries), 2)
        self.assertTrue(all("观夏" in q for q in queries))
        self.assertTrue(any("香" in q for q in queries))
        for q in queries:
            self.assertNotIn("brief", q.lower())

    def test_build_search_queries_uses_llm_provided_category(self):
        queries = _build_search_queries("某品牌", "无关正文", category="精品咖啡")
        self.assertTrue(any("精品咖啡" in q for q in queries))

    def test_parse_brand_entity_payload_strips_markdown_fence(self):
        raw = '```json\n{"brand_name":"观夏","product":"陶瓷香挂","category":"香氛"}\n```'
        entity = _parse_brand_entity_payload(raw)
        self.assertEqual(entity, {"brand_name": "观夏", "product": "陶瓷香挂", "category": "香氛"})

    def test_looks_like_valid_brand_rejects_noise_words(self):
        self.assertFalse(_looks_like_valid_brand(""))
        self.assertFalse(_looks_like_valid_brand("brief"))
        self.assertFalse(_looks_like_valid_brand("Brand"))
        self.assertFalse(_looks_like_valid_brand("合作"))
        self.assertTrue(_looks_like_valid_brand("观夏"))
        self.assertTrue(_looks_like_valid_brand("Nike"))


class LLMExtractBrandEntityTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_parsed_entity_on_real_response(self):
        fake_response = {
            "choices": [
                {"message": {"content": json.dumps({"brand_name": "观夏", "product": "陶瓷香挂", "category": "香氛"})}}
            ]
        }
        with patch("app.services.brand_brief_pipeline.LLMClient") as MockClient:
            MockClient.return_value.chat = AsyncMock(return_value=fake_response)
            entity = await _llm_extract_brand_entity(brief_text=SAMPLE_BRIEF, filename="观夏brief.md")
        self.assertEqual(entity["brand_name"], "观夏")
        self.assertEqual(entity["category"], "香氛")

    async def test_returns_empty_dict_on_mock_response(self):
        with patch("app.services.brand_brief_pipeline.LLMClient") as MockClient:
            MockClient.return_value.chat = AsyncMock(return_value={"mock": True, "payload": {}})
            entity = await _llm_extract_brand_entity(brief_text=SAMPLE_BRIEF, filename=None)
        self.assertEqual(entity, {})

    async def test_returns_empty_dict_on_llm_exception(self):
        with patch("app.services.brand_brief_pipeline.LLMClient") as MockClient:
            MockClient.return_value.chat = AsyncMock(side_effect=RuntimeError("boom"))
            entity = await _llm_extract_brand_entity(brief_text=SAMPLE_BRIEF, filename=None)
        self.assertEqual(entity, {})


if __name__ == "__main__":
    unittest.main()
