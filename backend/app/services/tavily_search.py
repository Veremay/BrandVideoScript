from typing import Any

import httpx

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


async def tavily_search(*, api_key: str, query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Tavily Search API — auth and base URL per https://docs.tavily.com/documentation/api-reference/introduction"""
    if not api_key or not query.strip():
        return []

    payload: dict[str, Any] = {
        "query": query.strip(),
        "max_results": max_results,
        "search_depth": "basic",
    }
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
    for item in results[:max_results]:
        snippets.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": (item.get("content") or item.get("snippet") or "")[:1200],
            }
        )
    return snippets
