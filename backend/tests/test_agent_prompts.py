from pathlib import Path

from app.services.agents import audience_agent, brand_agent


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
