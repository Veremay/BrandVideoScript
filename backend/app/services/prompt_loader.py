from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings

PROMPTS_ROOT = Path(__file__).resolve().parent.parent / "prompts"


class PromptTemplateError(Exception):
    pass


def prompts_dir() -> Path:
    """Return the language-specific prompts directory (prompts/zh or prompts/en)."""
    language = get_settings().prompt_language
    return PROMPTS_ROOT / language


def load_prompt(filename: str) -> str:
    """Load a prompt file for the active PROMPT_LANGUAGE.

    ``filename`` is relative to ``prompts/{zh|en}/``, e.g. ``brand_agent.md`` or
    ``tasks/brand_phase1_instructions.md``.
    """
    path = prompts_dir() / filename
    if not path.is_file():
        raise PromptTemplateError(
            f"Prompt file not found for language={get_settings().prompt_language!r}: {filename}"
        )
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise PromptTemplateError(
            f"Prompt file is empty for language={get_settings().prompt_language!r}: {filename}"
        )
    return text


def render_prompt(template: str, variables: dict[str, str]) -> str:
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered
