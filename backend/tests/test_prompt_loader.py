import tempfile
import unittest
from pathlib import Path

from app.services.prompt_loader import PromptLoader, PromptTemplateError


class PromptLoaderTest(unittest.TestCase):
    def test_renders_agent_prompt_with_context_variables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir)
            (prompts_dir / "brand.md").write_text(
                "Brand prompt\nBrief: {{brief_summary}}\nScript: {{script_summary}}",
                encoding="utf-8",
            )

            loader = PromptLoader(prompts_dir=prompts_dir)

            rendered = loader.render(
                "brand",
                {"brief_summary": "Launch brief", "script_summary": "3 rows"},
            )

            self.assertIn("Brand prompt", rendered)
            self.assertIn("Brief: Launch brief", rendered)
            self.assertIn("Script: 3 rows", rendered)

    def test_rejects_missing_prompt_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = PromptLoader(prompts_dir=Path(temp_dir))

            with self.assertRaisesRegex(PromptTemplateError, "Prompt file not found"):
                loader.render("brand", {})

    def test_rejects_empty_prompt_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir)
            (prompts_dir / "audience.md").write_text("   ", encoding="utf-8")
            loader = PromptLoader(prompts_dir=prompts_dir)

            with self.assertRaisesRegex(PromptTemplateError, "Prompt file is empty"):
                loader.render("audience", {})


if __name__ == "__main__":
    unittest.main()
