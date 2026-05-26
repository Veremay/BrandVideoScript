from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptTemplateError(Exception):
    pass


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.is_file():
        raise PromptTemplateError(f"Prompt file not found: {filename}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise PromptTemplateError(f"Prompt file is empty: {filename}")
    return text


def render_prompt(template: str, variables: dict[str, str]) -> str:
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered
