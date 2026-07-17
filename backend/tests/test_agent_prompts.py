from app.core.config import get_settings
from app.services.prompt_loader import load_prompt, prompts_dir


def test_brand_prompts_use_5w1h_without_forcing_questionnaire_output() -> None:
    phase1_text = load_prompt("tasks/brand_phase1_instructions.md")
    phase2_text = load_prompt("tasks/brand_phase2_instructions.md")

    for dimension in ("Who", "What", "Why", "When", "Where", "How"):
        assert f"**{dimension}**" in phase1_text

    assert "不要为了填满 5W1H 补造信息" in phase1_text
    assert "explicit_requirement" in phase1_text
    assert "implicit_requirement" in phase1_text
    assert "不要输出 5W1H 问答过程" in phase1_text
    assert "5W1H 立场完整性检查" in phase2_text
    assert "不要求每个立场机械覆盖全部六项" in phase2_text
    assert "5W1H 仅用于内部检查" in phase2_text


def test_map_update_prompts_require_perspective_tension() -> None:
    brand_text = load_prompt("tasks/brand_phase2_instructions.md")
    audience_text = load_prompt("tasks/audience_default_instructions.md")
    expert_text = load_prompt("expert_agent.md")
    coordinator_text = load_prompt("coordinator_agent.md")

    assert "Do not default to supporting the current script" in brand_text
    assert "brand requirements, risks, and non-negotiables" in brand_text
    assert "Every generated position must include a real argument" in brand_text
    assert "audience friction or drop-off risk" in audience_text
    assert "surface trade-offs" in audience_text
    assert "Every generated position must include a real argument" in audience_text
    assert "Do not default to supporting the current script" in expert_text
    assert "trade-off" in expert_text
    assert "Every generated position must include a real argument" in expert_text
    assert "Do not bury Brand or Audience viewpoints inside an Expert position" in expert_text
    assert "cannot be maximized at the same time" in coordinator_text
    assert "decision axis" in coordinator_text


def test_prompt_language_en_resolves_en_directory(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("PROMPT_LANGUAGE", "en")
    get_settings.cache_clear()
    try:
        assert prompts_dir().name == "en"
        assert "You are the **Brand Agent**" in load_prompt("brand_agent.md")
        assert "brand requirement extraction" in load_prompt("tasks/brand_phase1_instructions.md").lower()
        assert "AI writing assistant" in load_prompt("vanilla_system.md")
    finally:
        get_settings.cache_clear()
        monkeypatch.delenv("PROMPT_LANGUAGE", raising=False)
        get_settings.cache_clear()
