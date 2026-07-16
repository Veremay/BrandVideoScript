from typing import Literal

from tavily import AsyncTavilyClient

from app.core.config import get_settings
from app.services.app_log import log_activity, log_error, log_warning

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
            log_warning("Tavily search mock/disabled", query=query, mock=mock, enabled=self.enabled)
            return {"mock": True, "payload": payload, "results": []}

        log_activity(action="tavily.search", query=query, max_results=max_results, search_depth=search_depth)
        client = AsyncTavilyClient(api_key=self.settings.tavily_api_key)
        try:
            result = await client.search(
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
            log_activity(action="tavily.search.done", query=query, result_count=len(result.get("results") or []))
            return result
        except Exception as exc:
            log_error("Tavily search failed", exc=exc, query=query)
            raise
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
            log_warning("Tavily extract mock/disabled", url_count=len(urls), mock=mock, enabled=self.enabled)
            return {"mock": True, "payload": payload, "results": []}

        log_activity(action="tavily.extract", url_count=len(urls), extract_depth=extract_depth, format=format)
        client = AsyncTavilyClient(api_key=self.settings.tavily_api_key)
        try:
            result = await client.extract(
                urls=urls,
                extract_depth=extract_depth,
                format=format,
                query=query,
            )
            log_activity(action="tavily.extract.done", url_count=len(urls), result_count=len(result.get("results") or []))
            return result
        except Exception as exc:
            log_error("Tavily extract failed", exc=exc, url_count=len(urls))
            raise
        finally:
            await client.close()
