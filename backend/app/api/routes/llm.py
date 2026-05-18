from fastapi import APIRouter

from app.models.schemas import LLMChatRequest
from app.services.llm_client import LLMClient

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/mock-chat")
async def mock_chat(payload: LLMChatRequest) -> dict:
    client = LLMClient()
    return await client.chat(
        messages=payload.messages,
        task_type=payload.task_type,
        stream=payload.stream,
        response_format=payload.response_format,
        complexity=payload.complexity,
        mock=True,
    )

