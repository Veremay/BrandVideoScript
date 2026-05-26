from __future__ import annotations

from typing import Any


async def brand_wiki_lookup(brand_name: str | None = None, *, mock: bool = True) -> dict[str, Any]:
    """Stub Brand Wiki lookup for MVP."""
    label = brand_name or "品牌"
    return {
        "mock": mock,
        "brand_name": label,
        "snippets": [
            {
                "topic": "调性",
                "text": f"{label} 在公开资料中强调真实、克制的产品表达，避免夸张承诺。",
            },
            {
                "topic": "合作偏好",
                "text": "更倾向生活化场景与可验证的使用体验，而非纯口播促销。",
            },
        ],
    }
