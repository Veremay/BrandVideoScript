from typing import Literal

from tavily import AsyncTavilyClient

from app.core.config import get_settings

SearchDepth = Literal["basic", "advanced", "fast", "ultra-fast"]
SearchTopic = Literal["general", "news", "finance"]
SearchTimeRange = Literal["day", "week", "month", "year"]
ExtractDepth = Literal["basic", "advanced"]
ExtractFormat = Literal["markdown", "text"]


class TavilyClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.tavily_api_key)

    async def search(
        self,
        *,
        query: str,
        max_results: int = 5,
        search_depth: SearchDepth = "basic",
        topic: SearchTopic | None = None,
        time_range: SearchTimeRange | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        include_answer: bool | Literal["basic", "advanced"] = False,
        include_raw_content: bool | ExtractFormat = False,
        mock: bool = False,
    ) -> dict:
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "topic": topic,
            "time_range": time_range,
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
        }
        if mock or not self.enabled:
            return {"mock": True, "payload": payload, "results": []}

        client = AsyncTavilyClient(api_key=self.settings.tavily_api_key)
        try:
            return await client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                topic=topic,
                time_range=time_range,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                include_answer=include_answer,
                include_raw_content=include_raw_content,
            )
        finally:
            await client.close()

    async def extract(
        self,
        *,
        urls: list[str],
        extract_depth: ExtractDepth = "basic",
        format: ExtractFormat = "markdown",
        query: str | None = None,
        mock: bool = False,
    ) -> dict:
        payload = {
            "urls": urls,
            "extract_depth": extract_depth,
            "format": format,
            "query": query,
        }
        if mock or not self.enabled:
            return {"mock": True, "payload": payload, "results": []}

        client = AsyncTavilyClient(api_key=self.settings.tavily_api_key)
        try:
            return await client.extract(
                urls=urls,
                extract_depth=extract_depth,
                format=format,
                query=query,
            )
        finally:
            await client.close()
