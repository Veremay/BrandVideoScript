from __future__ import annotations

from typing import Any


async def domain_case_retriever(topic: str = "", *, mock: bool = True) -> dict[str, Any]:
    return {
        "mock": mock,
        "cases": [
            {
                "title": "生活化开箱结构",
                "structure": "痛点引入 → 真实使用 → 轻量总结 → 自然 CTA",
            }
        ],
    }


async def script_structure_kb(query: str = "", *, mock: bool = True) -> dict[str, Any]:
    return {
        "mock": mock,
        "patterns": [
            "前 5 秒给出观看理由",
            "中段用对比或前后变化建立可信度",
            "结尾保留创作者口吻的总结",
        ],
    }
