from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.model_router import select_model, should_enable_thinking


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


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

    async def stream_tokens(
        self,
        *,
        messages: list[dict[str, str]],
        task_type: str,
        complexity: str = "normal",
        mock: bool | None = None,
    ) -> AsyncIterator[str]:
        model = select_model(task_type, complexity)
        use_mock = mock if mock is not None else not self.settings.siliconflow_api_key
        if use_mock:
            text = await self._mock_reply(messages)
            for index in range(0, len(text), 12):
                yield text[index : index + 12]
                await asyncio.sleep(0.02)
            return

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.4,
            "top_p": 0.7,
            "enable_thinking": should_enable_thinking(task_type, complexity),
        }
        async with httpx.AsyncClient(base_url=self.settings.siliconflow_base_url, timeout=120) as client:
            async with client.stream(
                "POST",
                "/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.siliconflow_api_key}"},
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        data = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    delta = data.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta:
                        yield delta

    async def complete_json(
        self,
        *,
        messages: list[dict[str, str]],
        task_type: str,
        complexity: str = "high",
        mock: bool | None = None,
    ) -> dict[str, Any]:
        use_mock = mock if mock is not None else not self.settings.siliconflow_api_key
        if use_mock:
            raise RuntimeError("mock mode — caller should use fallback")

        response = await self.chat(
            messages=messages,
            task_type=task_type,
            stream=False,
            response_format={"type": "json_object"},
            complexity=complexity,
            mock=False,
        )
        content = self._extract_message_content(response)
        try:
            return extract_json_object(content)
        except (json.JSONDecodeError, ValueError):
            repair = await self.chat(
                messages=[
                    {"role": "system", "content": "Fix the JSON syntax only. Output valid JSON object, nothing else."},
                    {"role": "user", "content": content},
                ],
                task_type="coordinator_structured",
                stream=False,
                response_format={"type": "json_object"},
                complexity="normal",
                mock=False,
            )
            return extract_json_object(self._extract_message_content(repair))

    def _extract_message_content(self, response: dict[str, Any]) -> str:
        if response.get("mock"):
            raise RuntimeError("unexpected mock response in complete_json")
        choices = response.get("choices") or []
        if not choices:
            raise ValueError("LLM response missing choices")
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if not str(content).strip():
            raise ValueError("LLM response empty content")
        return str(content)

    async def _mock_reply(self, messages: list[dict[str, str]]) -> str:
        user_text = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        if not user_text:
            return "How can I help with your script today?"
        return (
            f"I reviewed your question: \"{user_text[:160]}\". "
            "Brand, Audience, and Expert perspectives were scheduled based on your chips. "
            "New IBIS nodes were added to the graph where relevant — open Node Graph to review them."
        )
