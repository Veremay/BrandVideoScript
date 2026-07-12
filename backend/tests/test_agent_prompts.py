from pathlib import Path

from app.services.agents import audience_agent, brand_agent


def test_brand_prompts_use_5w1h_without_forcing_questionnaire_output() -> None:
    phase1_text = brand_agent._PHASE1_TASK_INSTRUCTIONS
    phase2_text = brand_agent._PHASE2_TASK_INSTRUCTIONS

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
    brand_text = brand_agent._PHASE2_TASK_INSTRUCTIONS
    audience_text = audience_agent._DEFAULT_TASK_INSTRUCTIONS
    expert_text = (Path(__file__).parents[1] / "app" / "prompts" / "expert_agent.md").read_text(encoding="utf-8")
    coordinator_text = (Path(__file__).parents[1] / "app" / "prompts" / "coordinator_agent.md").read_text(encoding="utf-8")

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
