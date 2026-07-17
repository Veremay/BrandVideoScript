from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.model_router import select_model, should_enable_thinking
from app.services.pipeline_log import (
    log_llm_mock,
    log_llm_request,
    log_llm_response,
    log_llm_stream_end,
    log_llm_stream_start,
    log_llm_stream_token,
    log_step,
)


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
        }
        if should_enable_thinking(task_type, complexity):
            payload["enable_thinking"] = True
        if response_format is not None:
            payload["response_format"] = response_format

        log_llm_request(
            task_type=task_type,
            model=model,
            messages=messages,
            stream=stream,
            response_format=response_format,
        )

        if mock or not self.settings.siliconflow_api_key:
            log_llm_mock(task_type, reason="mock=True or missing API key")
            return {"mock": True, "payload": payload}

        timeout = self.settings.siliconflow_request_timeout_seconds
        async with httpx.AsyncClient(base_url=self.settings.siliconflow_base_url, timeout=timeout) as client:
            response = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.siliconflow_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            try:
                content = self._extract_message_content(data)
            except (RuntimeError, ValueError):
                content = json.dumps(data, ensure_ascii=False)
            log_llm_response(task_type=task_type, model=model, content=content)
            return data

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

        log_llm_request(task_type=task_type, model=model, messages=messages, stream=True)

        if use_mock:
            log_llm_mock(task_type, reason="stream mock mode")
            text = await self._mock_reply(messages)
            log_llm_response(task_type=task_type, model=model, content=text, extra="source=mock_stream")
            for index in range(0, len(text), 12):
                yield text[index : index + 12]
                await asyncio.sleep(0.02)
            return

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.4,
            "top_p": 0.7,
        }
        if should_enable_thinking(task_type, complexity):
            payload["enable_thinking"] = True
        collected: list[str] = []
        stream_timeout = self.settings.siliconflow_stream_timeout_seconds
        async with httpx.AsyncClient(base_url=self.settings.siliconflow_base_url, timeout=stream_timeout) as client:
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
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content")
                    if delta:
                        collected.append(delta)
                        yield delta
        log_llm_response(
            task_type=task_type,
            model=model,
            content="".join(collected),
            extra="source=stream",
        )

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

        model = select_model(task_type, complexity)
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
            parsed = extract_json_object(content)
            log_step(
                f"llm.complete_json.{task_type}",
                phase="OUT",
                parsed_json=parsed,
            )
            return parsed
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
            repaired_content = self._extract_message_content(repair)
            parsed = extract_json_object(repaired_content)
            log_llm_response(
                task_type=task_type,
                model=model,
                content=repaired_content,
                parsed_json=parsed,
                extra="source=complete_json_repair",
            )
            return parsed

    async def complete_json_via_stream(
        self,
        *,
        messages: list[dict[str, str]],
        task_type: str,
        complexity: str = "high",
        mock: bool | None = None,
    ) -> dict[str, Any]:
        """Same as complete_json but uses streaming to avoid ReadTimeout on slow models.

        The streaming endpoint emits tokens incrementally, so the per-read timeout
        (siliconflow_stream_timeout_seconds) only applies between chunks, not for the
        entire generation. This prevents timeouts on long-running requests.
        """
        use_mock = mock if mock is not None else not self.settings.siliconflow_api_key
        if use_mock:
            raise RuntimeError("mock mode — caller should use fallback")

        model = select_model(task_type, complexity)
        log_llm_request(task_type=task_type, model=model, messages=messages, stream=True)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.4,
            "top_p": 0.7,
        }
        if should_enable_thinking(task_type, complexity):
            payload["enable_thinking"] = True

        chunks: list[str] = []
        stream_timeout = self.settings.siliconflow_stream_timeout_seconds
        log_llm_stream_start(task_type, model)
        async with httpx.AsyncClient(base_url=self.settings.siliconflow_base_url, timeout=stream_timeout) as client:
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
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content")
                    if delta:
                        chunks.append(delta)
                        log_llm_stream_token(delta)
        log_llm_stream_end()

        content = "".join(chunks)
        log_llm_response(task_type=task_type, model=model, content=content, extra="source=stream")
        try:
            parsed = extract_json_object(content)
            log_step(f"llm.complete_json_via_stream.{task_type}", phase="OUT", parsed_json=parsed)
            return parsed
        except (json.JSONDecodeError, ValueError):
            repair = await self.complete_json_via_stream(
                messages=[
                    {"role": "system", "content": "Fix the JSON syntax only. Output valid JSON object, nothing else."},
                    {"role": "user", "content": content},
                ],
                task_type="coordinator_structured",
                complexity="normal",
                mock=False,
            )
            log_llm_response(
                task_type=task_type,
                model=model,
                content=json.dumps(repair, ensure_ascii=False),
                parsed_json=repair,
                extra="source=complete_json_via_stream_repair",
            )
            return repair

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
            "Brand, Audience, and Expert perspectives were scheduled by the Coordinator. "
            "New IBIS nodes were added to the graph where relevant — open Node Graph to review them."
        )
