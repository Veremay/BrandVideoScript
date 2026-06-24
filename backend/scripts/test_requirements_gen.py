"""
快速验证 requirements 生成效果。
用法：uv run python scripts/test_requirements_gen.py
"""
from __future__ import annotations

import asyncio
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BRIEF_TEXT = """\
### 📌【合作 brief】观夏 × 视频创作者：陶瓷香挂系列推广合作

#### 一、品牌介绍

**观夏 To Summer**，东方植物调香氛品牌。
我们坚持挖掘中国人记忆中的自然香气，以东方植物为灵感，融合全球优质原料与手工技艺，创作有呼吸感、留白感的香气作品。

---

#### 二、产品介绍：陶瓷香挂

**产品名称**：陶瓷香挂（Scented Ceramic Wax Tablet）
**香型示例**：颐和金桂、听泉茉莉、福开森路、金银花1990、昆仑煮雪等
**核心卖点**：
- **东方设计美学**：灵感来自东方园林窗棂，圆与方的摩登线条，素瓷质感，手工烧制
- **自然扩香**：天然植物精油融入蜡基，无需明火，持续扩香
- **情绪价值**：唤醒生活气息，把东方自然香带入日常空间
- **用法灵活**：挂于衣橱、抽屉、包包，或作为精致小礼物

---

#### 三、合作目标

1. 提升陶瓷香挂系列在年轻消费者中的认知与种草欲望
2. 传递观夏品牌的东方美学调性，而非单纯功能介绍
3. 自然展示产品使用场景，引发观看者共鸣

---

#### 四、内容方向建议

- 以"生活方式"切入，展示香挂在真实空间（家居、衣橱、出行）中的使用
- 着重传递香气带来的情绪价值和氛围感，而非参数罗列
- 可融入个人故事或东方文化意象，增强内容深度
- 避免过度强调价格或促销，保持品牌调性

---

#### 五、禁止事项

- ❌ 禁止对比竞品
- ❌ 不得出现"最好用""绝对""第一"等绝对化用语
- ❌ 不得宣称医疗/保健效果
- ❌ 不得使用与品牌调性不符的夸张/搞笑风格

---

#### 六、产品提供

寄送陶瓷香挂体验装（3款），供创作者真实体验后内容创作。
"""


def _print_section(title: str, items: list) -> None:
    print(f"\n{'─' * 55}")
    print(f"  {title}  ({len(items)} 条)")
    print(f"{'─' * 55}")
    if not items:
        print("  （空）")
        return
    for i, item in enumerate(items, 1):
        conf = item.get("confidence", "?")
        text = item.get("text", "")
        evidence = item.get("evidence", "")
        wrapped = textwrap.fill(text, width=70, initial_indent="  ", subsequent_indent="    ")
        print(f"{i}. [{conf}]\n{wrapped}")
        if evidence:
            ev_wrapped = textwrap.fill(evidence, width=68, initial_indent="    依据：", subsequent_indent="          ")
            print(ev_wrapped)


async def main() -> None:
    from app.services.agents.brand_agent import run_brand_agent  # noqa: PLC0415

    project = {
        "_id": "test_req_gen",
        "platform_context": "xiaohongshu",
        "brief": {
            "filename": "观夏陶瓷香挂合作brief.md",
            "text": BRIEF_TEXT,
            "parse_status": "pending",
        },
        "brand_perspective_result": None,
        "brand_insights": [],
        "personas": [],
        "active_persona_id": None,
        "current_script_version_id": "ver_test",
        "current_script": {"columns": [], "rows": []},
        "rationale_nodes": [],
        "rationale_edges": [],
    }

    print("\n  正在调用 Brand Agent (task_context=brief_parse)...\n", flush=True)
    result = await run_brand_agent(project, task_context="brief_parse")

    _print_section("显式需求（Explicit）", result.get("explicit_requirements", []))
    _print_section("隐性需求（Implicit）", result.get("implicit_requirements", []))

    constraints = result.get("constraints", [])
    print(f"\n{'─' * 55}")
    print(f"  创作约束  ({len(constraints)} 条)")
    print(f"{'─' * 55}")
    for c in constraints:
        print(f"  - {c}")

    pr_risks = result.get("pr_risks", [])
    print(f"\n{'─' * 55}")
    print(f"  审片风险  ({len(pr_risks)} 条)")
    print(f"{'─' * 55}")
    for r in pr_risks:
        print(f"  [!] {r}")

    print(f"\n{'─' * 55}")
    print(f"  品牌洞察  ({len(result.get('brand_insights', []))} 条)")
    print(f"{'─' * 55}")
    for ins in result.get("brand_insights", []):
        print(f"  [{ins.get('category')} / {ins.get('confidence')}] {ins.get('title')}")
        print(f"    {ins.get('content', '')[:120]}")

    nodes = result.get("proposed_nodes", [])
    print(f"\n{'─' * 55}")
    print(f"  IBIS 节点  ({len(nodes)} 条)")
    print(f"{'─' * 55}")
    for n in nodes:
        print(f"  [{n.get('node_type')} / {n.get('source_type')}] {n.get('title')}")

    print("\n[done]\n")


if __name__ == "__main__":
    asyncio.run(main())
