from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.agents import brand_agent
from app.services.tools import brand_wiki
from scripts import distill_brand_wiki


class BrandWikiTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.wiki_dir = Path(self.tmp.name)
        self.original_dir = brand_wiki.BRAND_WIKI_DIR
        self.original_wiki_root_dir = brand_wiki.BRAND_WIKI_ROOT_DIR
        brand_wiki.BRAND_WIKI_DIR = self.wiki_dir
        brand_wiki.BRAND_WIKI_ROOT_DIR = self.wiki_dir

    def tearDown(self) -> None:
        brand_wiki.BRAND_WIKI_DIR = self.original_dir
        brand_wiki.BRAND_WIKI_ROOT_DIR = self.original_wiki_root_dir
        self.tmp.cleanup()

    def _write_wiki_page(self, brand: str, filename: str, text: str) -> Path:
        brand_dir = brand_wiki.BRAND_WIKI_ROOT_DIR / brand
        brand_dir.mkdir(parents=True, exist_ok=True)
        page = brand_dir / filename
        page.write_text(text, encoding="utf-8")
        return page

    async def test_search_reads_wiki_pages_for_matching_brand(self) -> None:
        self._write_wiki_page(
            "Nimbus",
            "_index.md",
            "# Nimbus Brand Wiki\n\n- [[tone-style]]\n- [[prohibited-expressions]]\n",
        )
        self._write_wiki_page(
            "Nimbus",
            "tone-style.md",
            "# Tone And Style\n\naliases: tone, style\n\nNimbus prefers quiet confidence and documentary scenes.\n",
        )
        self._write_wiki_page(
            "Nimbus",
            "prohibited-expressions.md",
            "# Prohibited Expressions\n\naliases: banned, hard sell\n\nAvoid exaggerated cure claims.\n",
        )

        result = await brand_wiki.brand_wiki_search(
            "avoid hard sell claims",
            brand_identifier="Nimbus launch brief.md",
            brief_text="Nimbus creator campaign",
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["brand_name"], "Nimbus")
        self.assertEqual(result["results"][0]["path"], "Nimbus/prohibited-expressions.md")
        self.assertIn("exaggerated cure", result["results"][0]["snippet"])

        pages = await brand_wiki.brand_wiki_read([result["results"][0]["path"]])

        self.assertEqual(pages["pages"][0]["brand_name"], "Nimbus")
        self.assertEqual(pages["pages"][0]["page_id"], "prohibited-expressions")
        self.assertIn("Avoid exaggerated cure claims", pages["pages"][0]["content"])

    async def test_context_for_task_deduplicates_search_results_and_reads_topic_pages(self) -> None:
        self._write_wiki_page(
            "Nimbus",
            "_index.md",
            "# Nimbus Brand Wiki\n\n- [[brand-positioning]]\n- [[tone-style]]\n- [[prohibited-expressions]]\n",
        )
        self._write_wiki_page(
            "Nimbus",
            "brand-positioning.md",
            "# Brand Positioning\n\nNimbus is a calm everyday technology brand.\n",
        )
        self._write_wiki_page(
            "Nimbus",
            "tone-style.md",
            "# Tone And Style\n\nUse warm, restrained, specific language.\n",
        )
        self._write_wiki_page(
            "Nimbus",
            "prohibited-expressions.md",
            "# Prohibited Expressions\n\nDo not use miracle, cure, or hard-sell phrasing.\n",
        )

        context = await brand_wiki.brand_wiki_context_for_task(
            brand_identifier="Nimbus",
            brief_text="Nimbus wants a warm launch video without hard-sell claims.",
            task="extract_requirements",
        )

        self.assertTrue(context["found"])
        self.assertIn("## Brand Wiki Search", context["context"])
        self.assertIn("Nimbus/prohibited-expressions.md", context["context"])
        self.assertIn("Do not use miracle", context["context"])
        self.assertLessEqual(context["context"].count("Nimbus/prohibited-expressions.md"), 2)

    async def test_lookup_falls_back_to_distilled_manual_when_wiki_is_missing(self) -> None:
        manual = self.wiki_dir / "2026NimbusBrandManual.md"
        manual.write_text("Nimbus raw manual", encoding="utf-8")
        manual.with_suffix(".distilled.md").write_text("Nimbus distilled manual", encoding="utf-8")

        result = await brand_wiki.brand_wiki_lookup("2026NimbusBrandManual.md", brief_text="Nimbus")

        self.assertTrue(result["found"])
        self.assertEqual(result["full_text"], "Nimbus distilled manual")
        self.assertEqual(result["source"], "2026NimbusBrandManual.distilled.md")

    def test_compile_manual_to_wiki_writes_section_pages_without_inferred_topics(self) -> None:
        manual = self.wiki_dir / "2026NimbusBrandManual.md"
        manual.write_text(
            "# Nimbus Manual\n\n"
            "Opening note.\n\n"
            "## Take the Long View\n\n"
            "Build a forever product for commuters.\n\n"
            "## Make It Fun\n\n"
            "Use playful documentary scenes.\n",
            encoding="utf-8",
        )

        result = distill_brand_wiki.compile_manual_to_wiki(manual, output_root=self.wiki_dir)

        self.assertEqual(result["brand_name"], "Nimbus")
        self.assertTrue((self.wiki_dir / "Nimbus" / "_index.md").exists())
        self.assertTrue((self.wiki_dir / "Nimbus" / "manual" / "take-the-long-view.md").exists())
        self.assertFalse((self.wiki_dir / "Nimbus" / "prohibited-expressions.md").exists())
        self.assertTrue((self.wiki_dir / "Nimbus" / "error_book.yaml").exists())
        index = (self.wiki_dir / "Nimbus" / "_index.md").read_text(encoding="utf-8")
        section = (self.wiki_dir / "Nimbus" / "manual" / "take-the-long-view.md").read_text(encoding="utf-8")
        self.assertIn("[[manual/take-the-long-view]]", index)
        self.assertIn("Build a forever product", section)

    def test_compile_brand_directory_to_wiki_preserves_source_sections(self) -> None:
        source_dir = self.wiki_dir / "Duolingo"
        source_dir.mkdir()
        (source_dir / "The_Duolingo_Handbook.md").write_text(
            "# Letter from Luis\n\nDuolingo is quirky.\n\n"
            "## TL;DR\n\n# Take the Long View\n\nBuild a 100-year brand.\n\n"
            "# Make It Fun\n\nWholesome but unhinged.\n",
            encoding="utf-8",
        )
        (source_dir / "original_brand_guidelines.md").write_text(
            "# Writing - Brand narrative\n\nCapture the Duolingo story.\n\n"
            "## Principles\n\n### Inclusive\n\nEveryone is welcome.\n\n"
            "## Sample messaging\n\nEveryone can Duolingo.\n",
            encoding="utf-8",
        )
        (source_dir / "prohibited-expressions.md").write_text(
            "# Prohibited Expressions\n\nThis generated file should be ignored.\n",
            encoding="utf-8",
        )
        (source_dir / "_index.md").write_text("# Generated Index\n", encoding="utf-8")

        result = distill_brand_wiki.compile_brand_directory_to_wiki(source_dir, output_root=self.wiki_dir)

        brand_dir = self.wiki_dir / "Duolingo"
        self.assertEqual(result["brand_name"], "Duolingo")
        self.assertTrue((brand_dir / "handbook" / "take-the-long-view.md").exists())
        self.assertTrue((source_dir / "The_Duolingo_Handbook.md").exists())
        self.assertTrue((source_dir / "original_brand_guidelines.md").exists())
        self.assertTrue((brand_dir / "guidelines" / "principles" / "index.md").exists())
        self.assertTrue((brand_dir / "guidelines" / "principles" / "inclusive.md").exists())
        self.assertTrue((brand_dir / "_agent-guide.md").exists())
        self.assertFalse((brand_dir / "prohibited-expressions.md").exists())
        index = (brand_dir / "_index.md").read_text(encoding="utf-8")
        agent_guide = (brand_dir / "_agent-guide.md").read_text(encoding="utf-8")
        principles = (brand_dir / "guidelines" / "principles" / "inclusive.md").read_text(encoding="utf-8")
        self.assertIn("[[handbook/take-the-long-view]]", index)
        self.assertIn("[[guidelines/principles/index]]", index)
        self.assertIn("Everyone is welcome", principles)
        self.assertIn("## Inferred Topic Navigation", agent_guide)
        self.assertIn("[[guidelines/principles/inclusive]]", agent_guide)
        self.assertNotIn("prohibited-expressions.md", index)

    async def test_brand_agent_requirement_extraction_uses_curated_wiki_context(self) -> None:
        self._write_wiki_page(
            "Nimbus",
            "_index.md",
            "# Nimbus Brand Wiki\n\n- [[prohibited-expressions]]\n",
        )
        self._write_wiki_page(
            "Nimbus",
            "prohibited-expressions.md",
            "# Prohibited Expressions\n\nDo not use miracle, cure, or hard-sell phrasing.\n",
        )
        captured: dict[str, str] = {}

        async def fake_invoke_agent_json(**kwargs):
            captured["context"] = kwargs["context"]
            return {"constraints": [], "pr_risks": [], "brand_insights": []}

        project = {
            "_id": "project_1",
            "brief": {
                "filename": "Nimbus brief.md",
                "text": "Nimbus launch video should avoid hard-sell claims.",
            },
        }

        with patch.object(brand_agent, "invoke_agent_json", fake_invoke_agent_json):
            result = await brand_agent._run_requirements_extraction(project)

        self.assertIn("## Brand Wiki Search", captured["context"])
        self.assertIn("Nimbus/prohibited-expressions.md", captured["context"])
        self.assertIn("Do not use miracle", captured["context"])
        self.assertIn("brand_wiki_search", result["tool_calls_used"])
        self.assertIn("brand_wiki_read", result["tool_calls_used"])
        self.assertNotIn("brand_wiki_lookup", result["tool_calls_used"])


if __name__ == "__main__":
    unittest.main()
