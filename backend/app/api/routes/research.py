from fastapi import APIRouter, HTTPException

from app.models.schemas import TavilyExtractRequest, TavilySearchRequest
from app.services.tavily_client import TavilyClient

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/search")
async def search_web(payload: TavilySearchRequest) -> dict:
    client = TavilyClient()
    if not client.enabled and not payload.mock:
        raise HTTPException(status_code=503, detail="TAVILY_API_KEY is not configured")

    return await client.search(
        query=payload.query,
        max_results=payload.max_results,
        search_depth=payload.search_depth,
        topic=payload.topic,
        time_range=payload.time_range,
        include_domains=payload.include_domains,
        exclude_domains=payload.exclude_domains,
        include_answer=payload.include_answer,
        include_raw_content=payload.include_raw_content,
        mock=payload.mock,
    )


@router.post("/extract")
async def extract_urls(payload: TavilyExtractRequest) -> dict:
    client = TavilyClient()
    if not client.enabled and not payload.mock:
        raise HTTPException(status_code=503, detail="TAVILY_API_KEY is not configured")

    return await client.extract(
        urls=payload.urls,
        extract_depth=payload.extract_depth,
        format=payload.format,
        query=payload.query,
        mock=payload.mock,
    )
