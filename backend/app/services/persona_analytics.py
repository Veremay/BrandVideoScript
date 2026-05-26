from __future__ import annotations

from typing import Any, Literal, Protocol

from app.models.script import now_iso
from app.repositories.projects import build_persona

PlatformContext = Literal["xiaohongshu", "douyin", "bilibili", "other"]

PLATFORM_TEMPLATES: dict[str, dict[str, Any]] = {
    "xiaohongshu": {
        "name": "种草型年轻用户",
        "age_range": "18-28",
        "preferences": "真实测评、生活化场景、轻种草",
        "behavior": "刷到前 3 秒决定是否继续，反感硬广口播",
        "platform_context": "小红书",
        "ad_sensitivity": "high",
        "trust_trigger": ["真实使用体验", "细节展示", "创作者个人风格"],
        "reject_trigger": ["硬广话术", "过度滤镜", "夸大功效"],
    },
    "douyin": {
        "name": "快节奏娱乐观众",
        "age_range": "16-35",
        "preferences": "强节奏、信息密度高、情绪钩子",
        "behavior": "竖屏短注意力，喜欢反转与梗",
        "platform_context": "抖音",
        "ad_sensitivity": "medium",
        "trust_trigger": ["开头钩子", "真实反应", "剧情化植入"],
        "reject_trigger": ["拖沓铺垫", "生硬念稿", "虚假剧情"],
    },
    "bilibili": {
        "name": "深度内容爱好者",
        "age_range": "18-30",
        "preferences": "信息量、观点、幕后或技术拆解",
        "behavior": "愿意看完较长段落，对质量敏感",
        "platform_context": "B站",
        "ad_sensitivity": "low",
        "trust_trigger": ["专业讲解", "数据或对比", "创作者信誉"],
        "reject_trigger": ["低质剪辑", "敷衍植入", "标题党"],
    },
    "other": {
        "name": "泛平台观众",
        "age_range": "18-34",
        "preferences": "清晰价值点、真实表达",
        "behavior": "对广告敏感但接受自然植入",
        "platform_context": "综合平台",
        "ad_sensitivity": "medium",
        "trust_trigger": ["真诚表达", "场景贴合"],
        "reject_trigger": ["过度推销", "脱离场景"],
    },
}


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


class StubPersonaAnalyticsProvider:
    async def generate_personas(self, ctx: PersonaAnalyticsContext) -> list[dict[str, Any]]:
        template = PLATFORM_TEMPLATES.get(ctx.platform_context, PLATFORM_TEMPLATES["other"])
        name = template["name"]
        if ctx.brand_name:
            name = f"{ctx.brand_name} · {name}"
        persona = build_persona(
            name=name[:80],
            age_range=template["age_range"],
            preferences=template["preferences"],
            behavior=template["behavior"],
            platform_context=template["platform_context"],
            ad_sensitivity=template["ad_sensitivity"],
            trust_trigger=template["trust_trigger"],
            reject_trigger=template["reject_trigger"],
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
    return StubPersonaAnalyticsProvider()
