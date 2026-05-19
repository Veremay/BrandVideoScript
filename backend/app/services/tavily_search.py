from typing import Any

import httpx

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


async def tavily_search(
    *,
    api_key: str,
    query: str,
    max_results: int = 5,
    search_depth: str = "advanced",
    country: str | None = "china",
    topic: str = "general",
    min_score: float = 0.3,
    exclude_domains: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Tavily Search API — https://docs.tavily.com/documentation/api-reference/endpoint/search

    Defaults tuned for Chinese brand brief research:
    - advanced depth for higher relevance
    - country=china to bias toward 中文站点
    - score filter to drop low-quality hits (Tavily score is 0-1)
    """
    if not api_key or not query.strip():
        return []

    payload: dict[str, Any] = {
        "query": query.strip()[:380],
        "max_results": max(1, min(max_results, 20)),
        "search_depth": search_depth,
        "topic": topic,
    }
    if country:
        payload["country"] = country
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(TAVILY_SEARCH_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    results = data.get("results") or []
    snippets: list[dict[str, Any]] = []
    for item in results:
        score = float(item.get("score") or 0.0)
        if score < min_score:
            continue
        snippets.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": (item.get("content") or item.get("snippet") or "")[:1200],
                "score": round(score, 3),
            }
        )
        if len(snippets) >= max_results:
            break
    return snippets


async def tavily_search_many(
    *,
    api_key: str,
    queries: list[str],
    max_results_per_query: int = 4,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Run multiple queries; dedupe by URL, keep highest-score hit per source."""
    seen: dict[str, dict[str, Any]] = {}
    for q in queries:
        items = await tavily_search(api_key=api_key, query=q, max_results=max_results_per_query, **kwargs)
        for item in items:
            url = item.get("url") or ""
            if not url:
                continue
            existing = seen.get(url)
            if existing is None or item.get("score", 0) > existing.get("score", 0):
                merged = {**(existing or {}), **item}
                merged["queries"] = sorted(set((existing or {}).get("queries", []) + [q]))
                seen[url] = merged
    ranked = sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)
    return ranked
