"""
将 data/brand_wiki/ 中的品牌手册蒸馏为结构化摘要，供 Brand Agent 使用。

用法：
    uv run python scripts/distill_brand_wiki.py                  # 处理所有未蒸馏手册
    uv run python scripts/distill_brand_wiki.py --force           # 重新蒸馏所有手册
    uv run python scripts/distill_brand_wiki.py --file 2022观夏品牌手册.md
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WIKI_DIR = Path(__file__).resolve().parents[1] / "data" / "brand_wiki"

DISTILL_SYSTEM_PROMPT = """\
你是一位品牌内容策略专家，专注于帮助视频内容创作者理解品牌要求。

你的任务是阅读品牌方提供的品牌手册，提炼出对视频内容创作**最关键的品牌信息**，\
输出一份结构化、简洁的品牌摘要，供 AI 助手在后续判断合作内容需求时使用。

输出格式严格遵循以下 Markdown 结构，每个部分用 ## 标题分隔：

## 品牌定位
（2-3句：品牌是什么、面向谁、核心价值主张）

## 调性与风格
（用短语列举，例如：克制留白、东方意境、生活化场景、避免夸张……）

## 内容合作偏好
（列举该品牌希望内容如何呈现：偏好什么叙事方式、场景、情绪……）

## 明确禁止事项
（列举内容红线：不得出现什么、不得使用什么风格……）

## 品牌差异化
（1-2句：该品牌与同类产品的本质差异，用于帮助创作者理解品牌底气）

要求：
- 总字数控制在 700 字以内
- 保留品牌手册中出现的关键词和标志性表达
- 不要添加手册中没有的信息
- 若某部分手册中无明确内容，写"（手册未说明）"
"""

DISTILL_USER_TEMPLATE = """\
以下是品牌手册原文，请按格式提炼：

{full_text}
"""


async def distill_one(wiki_file: Path, *, force: bool = False) -> None:
    distilled_path = wiki_file.with_suffix(".distilled.md")

    if distilled_path.exists() and not force:
        print(f"  [skip] {wiki_file.name} — 已有蒸馏版本")
        return

    print(f"  [distill] {wiki_file.name} …")
    full_text = wiki_file.read_text(encoding="utf-8")

    from app.services.llm_client import LLMClient  # noqa: PLC0415

    client = LLMClient()
    if not client.settings.siliconflow_api_key:
        print("  [error] 未配置 SILICONFLOW_API_KEY，无法蒸馏")
        return

    import httpx  # noqa: PLC0415
    from app.services.model_router import select_model  # noqa: PLC0415

    model = select_model("brand_analyze_brief", "high")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": DISTILL_SYSTEM_PROMPT},
            {"role": "user", "content": DISTILL_USER_TEMPLATE.format(full_text=full_text)},
        ],
        "temperature": 0.3,
        "top_p": 0.8,
        "max_tokens": 1200,
    }

    async with httpx.AsyncClient(
        base_url=client.settings.siliconflow_base_url,
        timeout=180,
    ) as http:
        response = await http.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {client.settings.siliconflow_api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        print(f"  [error] LLM 未返回内容：{data}")
        return

    content: str = choices[0].get("message", {}).get("content", "").strip()
    if not content:
        print("  [error] LLM 返回内容为空")
        return

    # Prepend a header so the file is self-describing
    brand_name = wiki_file.stem
    header = f"<!-- 蒸馏自：{wiki_file.name}，请勿手动编辑，使用 distill_brand_wiki.py --force 重新生成 -->\n\n"
    distilled_path.write_text(header + content, encoding="utf-8")
    print(f"  [ok]     → {distilled_path.name}  ({len(content)} 字)")


async def main() -> None:
    parser = argparse.ArgumentParser(description="蒸馏品牌手册为结构化摘要")
    parser.add_argument("--force", action="store_true", help="强制重新蒸馏所有手册")
    parser.add_argument("--file", metavar="FILENAME", help="只处理指定文件名")
    args = parser.parse_args()

    if not WIKI_DIR.exists():
        print(f"[error] 目录不存在：{WIKI_DIR}")
        sys.exit(1)

    if args.file:
        targets = [WIKI_DIR / args.file]
        missing = [f for f in targets if not f.exists()]
        if missing:
            print(f"[error] 文件不存在：{missing[0]}")
            sys.exit(1)
    else:
        # Exclude already-distilled files and non-manual files
        targets = [
            f for f in sorted(WIKI_DIR.glob("*.md"))
            if ".distilled" not in f.stem
        ]

    if not targets:
        print("[info] 没有需要处理的文件")
        return

    print(f"\n处理 {len(targets)} 个手册文件：\n")
    for wiki_file in targets:
        await distill_one(wiki_file, force=args.force)

    print("\n完成\n")


if __name__ == "__main__":
    asyncio.run(main())
