from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Protocol

from app.models.script import now_iso
from app.repositories.projects import build_persona

PlatformContext = Literal["xiaohongshu", "douyin", "bilibili", "other"]

DEFAULT_PERSONAS_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "personas" / "14_personas_with_evidence.json"
)


class PersonaAnalyticsContext:
    def __init__(
        self,
        *,
        project_id: str,
        platform_context: PlatformContext = "other",
        content_category: str | None = None,
        brand_name: str | None = None,
        video_topic: str | None = None,
        locale: str = "zh-CN",
    ) -> None:
        self.project_id = project_id
        self.platform_context = platform_context
        self.content_category = content_category
        self.brand_name = brand_name
        self.video_topic = video_topic
        self.locale = locale


class PersonaAnalyticsProvider(Protocol):
    async def generate_personas(self, ctx: PersonaAnalyticsContext) -> list[dict[str, Any]]:
        ...


def _load_personas_payload(path: Path = DEFAULT_PERSONAS_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _persona_from_analytics_entry(entry: dict[str, Any], *, source_file: str) -> dict[str, Any]:
    persona = build_persona(
        name=str(entry.get("name") or "未命名观众")[:80],
        job=str(entry.get("job") or ""),
        explanation=str(entry.get("explanation") or ""),
        reason=str(entry.get("reason") or ""),
        personal_experiences=entry.get("personal_experiences") if isinstance(entry.get("personal_experiences"), list) else [],
        characteristic_values=entry.get("characteristic_values") if isinstance(entry.get("characteristic_values"), dict) else {},
        data_source="imported_data",
    )
    persona["analytics_meta"] = {
        "provider": "proxona_file",
        "source_file": source_file,
        "method": entry.get("method"),
        "cluster_id": entry.get("cluster_id"),
        "cluster_size": entry.get("cluster_size"),
        "generated_at": now_iso(),
    }
    return persona


class FilePersonaAnalyticsProvider:
    def __init__(self, personas_file: Path = DEFAULT_PERSONAS_FILE) -> None:
        self.personas_file = personas_file

    async def generate_personas(self, ctx: PersonaAnalyticsContext) -> list[dict[str, Any]]:
        payload = _load_personas_payload(self.personas_file)
        source_file = self.personas_file.name
        personas: list[dict[str, Any]] = []
        for entry in payload.get("personas", []):
            if not isinstance(entry, dict):
                continue
            personas.append(_persona_from_analytics_entry(entry, source_file=source_file))
        if not personas:
            raise ValueError("No personas found in analytics file")
        return personas


class StubPersonaAnalyticsProvider:
    """Minimal provider for tests and offline fallbacks."""

    async def generate_personas(self, ctx: PersonaAnalyticsContext) -> list[dict[str, Any]]:
        persona = build_persona(
            name="测试观众",
            job="测试职业",
            explanation="用于单元测试的占位人物简介。",
            reason="测试观看动机。",
            personal_experiences=["测试经历一", "测试经历二"],
            characteristic_values={"测试维度": "测试特征"},
            data_source="system_generated",
        )
        persona["analytics_meta"] = {
            "provider": "stub",
            "model_version": "phase2-stub-v1",
            "generated_at": now_iso(),
            "content_category": ctx.content_category,
            "video_topic": ctx.video_topic,
        }
        return [persona]


def get_persona_analytics_provider() -> PersonaAnalyticsProvider:
    return FilePersonaAnalyticsProvider()
