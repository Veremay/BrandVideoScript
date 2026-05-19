from pathlib import Path


AGENT_PROMPT_FILES = {
    "brand": "brand.md",
    "audience": "audience.md",
    "expert": "expert.md",
}


class PromptTemplateError(RuntimeError):
    pass


class PromptLoader:
    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir = prompts_dir or Path(__file__).resolve().parents[1] / "prompts"

    def render(self, agent_type: str, variables: dict[str, str]) -> str:
        filename = AGENT_PROMPT_FILES.get(agent_type)
        if filename is None:
            raise PromptTemplateError(f"Unsupported agent type: {agent_type}")

        path = self.prompts_dir / filename
        if not path.exists():
            raise PromptTemplateError(f"Prompt file not found: {path}")

        template = path.read_text(encoding="utf-8").strip()
        if not template:
            raise PromptTemplateError(f"Prompt file is empty: {path}")

        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered
