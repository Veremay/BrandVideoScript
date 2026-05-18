from typing import Any

import httpx

from app.core.config import get_settings
from app.services.model_router import select_model, should_enable_thinking


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        task_type: str,
        stream: bool = False,
        response_format: dict[str, Any] | None = None,
        complexity: str = "normal",
        mock: bool = True,
    ) -> dict[str, Any]:
        model = select_model(task_type, complexity)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.4,
            "top_p": 0.7,
            "enable_thinking": should_enable_thinking(task_type, complexity),
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if mock or not self.settings.siliconflow_api_key:
            return {"mock": True, "payload": payload}

        async with httpx.AsyncClient(base_url=self.settings.siliconflow_base_url, timeout=60) as client:
            response = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.siliconflow_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

