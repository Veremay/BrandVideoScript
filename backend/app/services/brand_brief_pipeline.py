import json
import re
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.paths import default_llm_wiki_root
from app.models.script import now_iso
from app.repositories.projects import build_brand_insight, filter_insights_preserve_user_and_feedback, get_project
from app.services.brand_wiki import extract_wiki_snippets, find_brand_slug_from_wiki
from app.services.llm_client import LLMClient, _describe_exception
from app.services.tavily_search import tavily_search_many
from app.services.trace import TraceRecorder

BRAND_EXTRACT_INSTRUCTION = """你是品牌合作 brief 的实体抽取助手。
从给定 Brief 正文中提取**主品牌名**（合作方品牌，不是创作者 / 平台名）。

只输出一个 JSON 对象，禁止 Markdown / 注释 / 多余字段：
{"brand_name":"短名称","product":"产品/系列名（可选，没有就空字符串）","category":"产品大类，如 香氛/护肤/数码/服装/咖啡 等，没有就空字符串"}

规则：
- brand_name 必须是 Brief 中真实出现的实体；优先取 markdown 加粗 `**X**`、`X × Y`、「品牌名：X」等强信号
- 若 Brief 同时含英文与中文名（如「观夏 To Summer」），brand_name 用中文主名
- 严禁输出 "brief"、"campaign"、"合作"、文件名片段
- 严禁编造任何 Brief 未出现的品牌
"""


INSIGHTS_JSON_INSTRUCTION = """你是品牌合作 brief 分析师。根据 Brief 正文、内部品牌手册片段、公开检索摘要，输出显式需求与隐式需求。
只输出一个 JSON 对象，不要 Markdown，不要解释。格式严格如下：
{"insights":[
  {
    "category":"explicit_requirement"|"implicit_requirement",
    "title":"短标题",
    "content":"可执行的需求描述",
    "reason":"推断依据",
    "confidence":"high"|"medium"|"low",
    "evidence":[{"source_type":"brief"|"brand_wiki"|"web","quote":"摘录原文"}]
  }
]}
至少 2 条 explicit_requirement，至少 2 条 implicit_requirement。evidence 的 quote 必须来自输入材料。"""


def _wiki_root() -> Path:
    settings = get_settings()
    if settings.brand_wiki_root.strip():
        return Path(settings.brand_wiki_root).expanduser().resolve()
    return default_llm_wiki_root()


_FILENAME_NOISE_RE = re.compile(
    r"(brief|brand[\s\-_]?brief|合作brief|合作简报|brand|campaign|稿件|稿子|品牌简报)",
    flags=re.IGNORECASE,
)


def _clean_filename_stem(filename: str | None) -> str:
    if not filename:
        return ""
    stem = Path(filename).stem
    cleaned = _FILENAME_NOISE_RE.sub("", stem)
    cleaned = re.sub(r"[\s\-_·.×x✕]+", "", cleaned).strip()
    return cleaned


def _parse_brand_entity_payload(raw: str) -> dict[str, str]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("brand_name", "product", "category"):
        value = data.get(key)
        if isinstance(value, str):
            out[key] = value.strip()
    return out


def _looks_like_valid_brand(name: str) -> bool:
    name = (name or "").strip()
    if not name or len(name) > 40:
        return False
    lower = name.lower()
    blocklist = {"brief", "brand", "campaign", "合作", "未知", "n/a", "none", "null", ""}
    if lower in blocklist:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", name))


async def _llm_extract_brand_entity(
    *,
    brief_text: str,
    filename: str | None,
    trace: TraceRecorder | None = None,
) -> dict[str, str]:
    """Cheap 8B call to pull brand_name / product / category from the brief. Empty dict on failure."""
    head = brief_text[:2000]
    user_content = (
        f"## 文件名\n{filename or '(无)'}\n\n"
        f"## Brief 正文（截断 2000 字）\n{head}\n"
    )
    client = LLMClient()
    try:
        result = await client.chat(
            messages=[
                {"role": "system", "content": BRAND_EXTRACT_INSTRUCTION},
                {"role": "user", "content": user_content},
            ],
            task_type="brand_extract_entity",
            stream=False,
            complexity="normal",
            mock=False,
            trace=trace,
        )
    except Exception:
        return {}

    if result.get("mock"):
        return {}

    try:
        choices = result.get("choices") or []
        message = choices[0].get("message") or {}
        raw_content = str(message.get("content") or "").strip()
    except (IndexError, KeyError, TypeError):
        return {}

    if not raw_content:
        return {}

    try:
        return _parse_brand_entity_payload(raw_content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _extract_brand_name(brief_text: str, filename: str | None) -> str:
    """Best-effort brand entity extraction; runs before LLM to ground search queries."""
    head = brief_text[:1500]

    for pattern in (
        r"\*\*([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9\s·\-]{1,30})\s+(?:To|For|×|x)\s+[^*]{1,40}\*\*",
        r"品牌名[称]?[：:]\s*\*?\*?([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9\s·\-]{1,30})\*?\*?",
        r"\*\*([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9\s·\-]{1,20})\s+(?:To\s+Summer|官方)",
        r"\*\*([\u4e00-\u9fff]{2,8})\*\*",
    ):
        m = re.search(pattern, head)
        if m:
            return m.group(1).strip()

    cleaned = _clean_filename_stem(filename)
    if cleaned:
        return cleaned

    for line in head.splitlines():
        line = line.strip().lstrip("#").strip()
        if not line or len(line) > 80:
            continue
        cn_match = re.search(r"([\u4e00-\u9fff]{2,8})", line)
        if cn_match and any(kw in line for kw in ("品牌", "合作", "推广", "campaign", "brief")):
            return cn_match.group(1)

    cn_match = re.search(r"[\u4e00-\u9fff]{2,8}", head)
    if cn_match:
        return cn_match.group(0)
    return "brand"


def _build_search_queries(
    brand_name: str,
    brief_text: str,
    *,
    product: str = "",
    category: str = "",
) -> list[str]:
    head = " ".join(brief_text.split())[:400].lower()
    product_hint = (product or "").strip()
    category_hint = (category or "").strip()
    if not category_hint:
        for kw in ("香薰", "香氛", "护肤", "美妆", "饮料", "咖啡", "手机", "汽车", "服装", "鞋", "运动", "数码", "家电", "母婴"):
            if kw in head:
                category_hint = kw
                break

    queries = [
        f"{brand_name} 品牌调性 内容风格",
        f"{brand_name} 创作者合作 视频内容",
    ]
    if category_hint:
        queries.append(f"{brand_name} {category_hint} 产品定位 用户口碑")
    if product_hint and product_hint not in queries[0]:
        queries.append(f"{brand_name} {product_hint} 用户评价")
    return queries[:4]


def _build_research_summary(brief_text: str, wiki_snippets: list[dict], web_snippets: list[dict]) -> str:
    parts: list[str] = []
    head = " ".join(line.strip() for line in brief_text.splitlines() if line.strip())[:400]
    parts.append(f"Brief 摘录：{head}")
    if wiki_snippets:
        parts.append("内部手册要点：" + " / ".join(s.get("heading", "") for s in wiki_snippets[:3]))
    if web_snippets:
        parts.append("公开来源要点：" + " / ".join(s.get("title", "") for s in web_snippets[:3]))
    return " ".join(parts)[:900]


def _parse_insights_payload(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text)
    items = data.get("insights")
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cat = item.get("category")
        if cat not in {"explicit_requirement", "implicit_requirement"}:
            continue
        title = str(item.get("title") or "").strip() or "未命名"
        content = str(item.get("content") or "").strip() or title
        reason = str(item.get("reason") or "").strip()
        conf = item.get("confidence") or "medium"
        if conf not in {"high", "medium", "low"}:
            conf = "medium"
        evidence = item.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        cleaned_ev: list[dict[str, Any]] = []
        for ev in evidence[:6]:
            if not isinstance(ev, dict):
                continue
            st = ev.get("source_type") or "brief"
            if st not in {"brief", "brand_wiki", "web", "pr_feedback", "script", "chat"}:
                st = "brief"
            q = str(ev.get("quote") or "").strip()[:500]
            if q:
                cleaned_ev.append({"source_type": st, "quote": q})
        if not cleaned_ev:
            cleaned_ev.append({"source_type": "brief", "quote": content[:240]})
        out.append(
            {
                "category": cat,
                "title": title,
                "content": content,
                "reason": reason or "由 Brief 与检索材料归纳。",
                "confidence": conf,
                "evidence": cleaned_ev,
            }
        )
    return out


def _mock_insights(brief_text: str) -> list[dict[str, Any]]:
    line = next((ln.strip() for ln in brief_text.splitlines() if ln.strip()), brief_text[:120])
    return [
        {
            "category": "explicit_requirement",
            "title": "Brief 直接要求（离线占位）",
            "content": line[:400] or "请在上传的真实 Brief 中写明产品卖点与必提信息。",
            "reason": "当前未配置 SILICONFLOW_API_KEY 或 LLM 返回 mock，使用占位洞察。",
            "confidence": "low",
            "evidence": [{"source_type": "brief", "quote": line[:200]}],
        },
        {
            "category": "explicit_requirement",
            "title": "格式与交付",
            "content": "按品牌方确认的成片时长、画幅与字幕规范交付。",
            "reason": "常见 brief 条款的通用归纳。",
            "confidence": "medium",
            "evidence": [{"source_type": "brief", "quote": line[:120]}],
        },
        {
            "category": "implicit_requirement",
            "title": "内容安全与合规",
            "content": "避免夸大疗效、对比贬损竞品与敏感话题，预留审片修改空间。",
            "reason": "品牌合作视频的常见隐式约束。",
            "confidence": "medium",
            "evidence": [{"source_type": "brief", "quote": line[:80]}],
        },
        {
            "category": "implicit_requirement",
            "title": "创作者真实感",
            "content": "保持创作者口吻与自然场景，降低硬广感以维护受众信任。",
            "reason": "独立创作者合作品牌的常见隐性期待。",
            "confidence": "medium",
            "evidence": [{"source_type": "brief", "quote": line[:80]}],
        },
    ]


async def _call_llm_for_insights(
    *,
    brief_text: str,
    brief_summary: str,
    research_summary: str,
    wiki_snippets: list[dict],
    web_snippets: list[dict],
    trace: TraceRecorder | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    wiki_block = "\n".join(f"- [{s.get('heading')}] {s.get('snippet', '')[:500]}" for s in wiki_snippets[:6])
    web_block = "\n".join(f"- {s.get('title')} {s.get('url')}\n  {s.get('snippet', '')[:400]}" for s in web_snippets[:5])

    user_content = f"""## Brief 摘要
{brief_summary}

## Brief 正文（截断）
{brief_text[:6000]}

## 检索归纳
{research_summary}

## 内部手册片段
{wiki_block or "（无）"}

## 公开检索片段
{web_block or "（无）"}
"""

    client = LLMClient()
    result = await client.chat(
        messages=[
            {"role": "system", "content": INSIGHTS_JSON_INSTRUCTION},
            {"role": "user", "content": user_content},
        ],
        task_type="brand_generate_insights",
        stream=False,
        complexity="high",
        mock=False,
        trace=trace,
    )

    if result.get("mock") or not settings.siliconflow_api_key:
        return _mock_insights(brief_text)

    try:
        choices = result.get("choices") or []
        message = choices[0].get("message") or {}
        raw_content = message.get("content") or ""
    except (IndexError, KeyError, TypeError):
        return _mock_insights(brief_text)

    if not raw_content.strip():
        return _mock_insights(brief_text)

    try:
        return _parse_insights_payload(raw_content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return _mock_insights(brief_text)


def _brand_research_payload(
    trace: TraceRecorder,
    *,
    status: str,
    brand_slug: str | None,
    matched_wiki: bool,
    queries: list[str],
    web_snippets: list[dict],
    wiki_snippets: list[dict],
    research_summary: str,
    entity: dict[str, str] | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    base = {
        "status": status,
        "brand_slug": brand_slug,
        "matched_wiki": matched_wiki,
        "queries": queries,
        "web_snippets": web_snippets,
        "wiki_snippets": wiki_snippets,
        "research_summary": research_summary,
        "entity": entity or {},
        "error_message": error_message,
        "updated_at": now_iso(),
    }
    return trace.merge_brand_research(base)


async def run_brand_brief_pipeline(db: Any, project_id: str, user_id: str) -> None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return

    brief = project.get("brief") or {}
    if brief.get("parse_status") != "parsed":
        return

    brief_text = brief.get("text") or ""
    brief_summary = brief.get("summary") or ""
    filename = brief.get("filename")
    settings = get_settings()
    wiki_root = _wiki_root()

    existing_br = project.get("brand_research") or {}
    trace = TraceRecorder(
        source="brand_brief_pipeline",
        run_id=existing_br.get("trace_run_id"),
        initial_events=existing_br.get("traces") or [],
    )
    trace.pipeline_started()

    try:
        trace.tool_call(
            "wiki_match",
            {"wiki_root": str(wiki_root), "filename": filename, "brief_chars": len(brief_text)},
        )
        brand_slug, meta_matched = find_brand_slug_from_wiki(wiki_root, filename, brief_text)
        trace.tool_result(
            "wiki_match",
            {"brand_slug": brand_slug, "meta_matched": meta_matched},
        )

        trace.tool_call("wiki_extract", {"brand_slug": brand_slug})
        wiki_snippets = extract_wiki_snippets(wiki_root, brand_slug, brief_text)
        matched_wiki = bool(wiki_snippets)
        trace.tool_result(
            "wiki_extract",
            {
                "snippet_count": len(wiki_snippets),
                "headings": [s.get("heading") for s in wiki_snippets[:5]],
            },
        )

        trace.tool_call("brand_entity_extract", {"filename": filename, "brief_chars": len(brief_text)})
        entity = await _llm_extract_brand_entity(brief_text=brief_text, filename=filename, trace=trace)
        llm_brand = entity.get("brand_name", "")
        if _looks_like_valid_brand(llm_brand):
            brand_name = llm_brand
            entity_source = "llm"
        else:
            brand_name = _extract_brand_name(brief_text, filename)
            entity_source = "heuristic_fallback"
        product = entity.get("product", "")
        category = entity.get("category", "")
        trace.tool_result(
            "brand_entity_extract",
            {
                "brand_name": brand_name,
                "product": product,
                "category": category,
                "source": entity_source,
            },
        )

        queries: list[str] = []
        web_snippets: list[dict[str, Any]] = []
        if settings.tavily_api_key:
            queries = _build_search_queries(brand_name, brief_text, product=product, category=category)
            trace.tool_call(
                "tavily_search",
                {
                    "brand_name": brand_name,
                    "queries": queries,
                    "search_depth": "advanced",
                    "country": "china",
                    "min_score": 0.3,
                },
            )
            try:
                web_snippets = await tavily_search_many(
                    api_key=settings.tavily_api_key,
                    queries=queries,
                    max_results_per_query=4,
                    search_depth="advanced",
                    country="china",
                    min_score=0.3,
                )
                web_snippets = web_snippets[:6]
                trace.tool_result(
                    "tavily_search",
                    {
                        "result_count": len(web_snippets),
                        "titles": [
                            {"title": s.get("title"), "score": s.get("score")}
                            for s in web_snippets[:6]
                        ],
                    },
                )
            except Exception as exc:
                web_snippets = []
                trace.tool_result("tavily_search", {"result_count": 0}, error=str(exc))
        else:
            queries.append("(Tavily 未配置 TAVILY_API_KEY)")
            trace.tool_result(
                "tavily_search",
                {"skipped": True, "reason": "TAVILY_API_KEY not configured"},
            )

        research_summary = _build_research_summary(brief_text, wiki_snippets, web_snippets)
        wiki_for_store = [{k: v for k, v in s.items() if k != "score"} for s in wiki_snippets]
        entity_payload = {
            "brand_name": brand_name,
            "product": product,
            "category": category,
            "source": entity_source,
        }

        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "brand_research": _brand_research_payload(
                        trace,
                        status="running",
                        brand_slug=brand_slug,
                        matched_wiki=matched_wiki or meta_matched,
                        queries=queries,
                        web_snippets=web_snippets,
                        wiki_snippets=wiki_for_store,
                        research_summary=research_summary,
                        entity=entity_payload,
                    ),
                    "updated_at": now_iso(),
                }
            },
        )

        raw_items = await _call_llm_for_insights(
            brief_text=brief_text,
            brief_summary=brief_summary,
            research_summary=research_summary,
            wiki_snippets=wiki_snippets,
            web_snippets=web_snippets,
            trace=trace,
        )

        refreshed = await get_project(db, project_id, user_id)
        base_insights = filter_insights_preserve_user_and_feedback((refreshed or project).get("brand_insights", []))

        new_insights: list[dict[str, Any]] = []
        for item in raw_items[:16]:
            new_insights.append(
                build_brand_insight(
                    category=item["category"],
                    title=item["title"],
                    content=item["content"],
                    reason=item["reason"],
                    evidence=item["evidence"],
                    confidence=item["confidence"],
                    status="new",
                    created_by="agent",
                )
            )

        merged = base_insights + new_insights
        trace.pipeline_completed(insight_count=len(new_insights))

        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "brand_insights": merged,
                    "brand_research": _brand_research_payload(
                        trace,
                        status="done",
                        brand_slug=brand_slug,
                        matched_wiki=matched_wiki or meta_matched,
                        queries=queries,
                        web_snippets=web_snippets,
                        wiki_snippets=wiki_for_store,
                        research_summary=research_summary,
                        entity=entity_payload,
                    ),
                    "stale.brand": False,
                    "stale.expert": True,
                    "updated_at": now_iso(),
                }
            },
        )
    except Exception as exc:  # noqa: BLE001 — pipeline must not crash the worker
        described = _describe_exception(exc)
        trace.pipeline_failed(error=described)
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "brand_research": _brand_research_payload(
                        trace,
                        status="failed",
                        brand_slug=None,
                        matched_wiki=False,
                        queries=[],
                        web_snippets=[],
                        wiki_snippets=[],
                        research_summary="",
                        error_message=described[:500],
                    ),
                    "updated_at": now_iso(),
                }
            },
        )
