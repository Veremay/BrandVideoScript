from app.core.config import get_settings
from app.services.prompt_loader import load_prompt
from app.services.vanilla_argue import (
    build_vanilla_argue_append_block,
    build_vanilla_argue_prompt,
    format_argue_item,
    scene_number_for_row,
)


def test_scene_number_for_row_uses_order() -> None:
    script = {
        "rows": [
            {"row_id": "r2", "order": 2},
            {"row_id": "r1", "order": 1},
            {"row_id": "r3", "order": 3},
        ]
    }
    assert scene_number_for_row(script, "r1") == 1
    assert scene_number_for_row(script, "r2") == 2
    assert scene_number_for_row(script, "r3") == 3


def test_vanilla_argue_prompt_zh_includes_scene_line(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("PROMPT_LANGUAGE", "zh")
    get_settings.cache_clear()
    try:
        assert "第2幕，{{" not in load_prompt("vanilla_argue_prompt.md")
        assert "{{items}}" in load_prompt("vanilla_argue_prompt.md")
        assert format_argue_item(2, "请在前三秒露出产品名") == "第2幕，请在前三秒露出产品名"
        prompt = build_vanilla_argue_prompt(2, "请在前三秒露出产品名")
        assert "第2幕，请在前三秒露出产品名" in prompt
        assert "建议我采取的立场" in prompt
        assert '"""' not in prompt
        append_block = build_vanilla_argue_append_block(3, "再加一条反馈")
        assert append_block == "第3幕，再加一条反馈"
    finally:
        get_settings.cache_clear()
        monkeypatch.delenv("PROMPT_LANGUAGE", raising=False)
        get_settings.cache_clear()


def test_vanilla_argue_prompt_en_includes_scene_line(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("PROMPT_LANGUAGE", "en")
    get_settings.cache_clear()
    try:
        assert "{{items}}" in load_prompt("vanilla_argue_prompt.md")
        assert format_argue_item(2, "Show the product name") == "Scene 2, Show the product name"
        prompt = build_vanilla_argue_prompt(2, "Show the product name in the first 3 seconds")
        assert "Scene 2, Show the product name in the first 3 seconds" in prompt
        assert "suggested stance" in prompt
        assert '"""' not in prompt
        append_block = build_vanilla_argue_append_block(3, "Another piece of feedback")
        assert append_block == "Scene 3, Another piece of feedback"
    finally:
        get_settings.cache_clear()
        monkeypatch.delenv("PROMPT_LANGUAGE", raising=False)
        get_settings.cache_clear()
