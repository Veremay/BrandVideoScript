from collections.abc import AsyncIterator
import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.model_router import select_model, should_enable_thinking
from app.services.trace import TraceRecorder


class LLMConfigurationError(RuntimeError):
    pass


def _describe_exception(exc: BaseException) -> str:
    """httpx timeout exceptions stringify to ''; return type + message so traces stay useful."""
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


def extract_stream_delta(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    return delta.get("content") or ""


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
        trace: TraceRecorder | None = None,
    ) -> dict[str, Any]:
        model = select_model(task_type, complexity)
        is_mock = mock or not self.settings.siliconflow_api_key
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
        if trace is not None:
            trace.llm_request(
                task_type=task_type,
                model=model,
                messages=messages,
                stream=stream,
                mock=is_mock,
            )
        if is_mock:
            result = {"mock": True, "payload": payload}
            if trace is not None:
                trace.llm_response(task_type=task_type, model=model, mock=True, raw=result)
            return result

        try:
            async with httpx.AsyncClient(
                base_url=self.settings.siliconflow_base_url,
                timeout=self.settings.siliconflow_chat_timeout,
            ) as client:
                response = await client.post(
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.siliconflow_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
        except Exception as exc:
            if trace is not None:
                trace.llm_response(
                    task_type=task_type,
                    model=model,
                    mock=False,
                    error=_describe_exception(exc),
                )
            raise

        if trace is not None:
            trace.llm_response(task_type=task_type, model=model, mock=False, raw=result)
        return result

    async def stream_chat(
        self,
        *,
        messages: list[dict[str, str]],
        task_type: str,
        response_format: dict[str, Any] | None = None,
        complexity: str = "normal",
        trace: TraceRecorder | None = None,
    ) -> AsyncIterator[str]:
        if not self.settings.siliconflow_api_key:
            raise LLMConfigurationError("SILICONFLOW_API_KEY is not configured")

        model = select_model(task_type, complexity)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.4,
            "top_p": 0.7,
            "enable_thinking": should_enable_thinking(task_type, complexity),
        }
        if response_format is not None:
            payload["response_format"] = response_format

        if trace is not None:
            trace.llm_request(task_type=task_type, model=model, messages=messages, stream=True, mock=False)

        collected: list[str] = []
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.siliconflow_base_url,
                timeout=self.settings.siliconflow_stream_timeout,
            ) as client:
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
                        raw_data = line.removeprefix("data:").strip()
                        if not raw_data or raw_data == "[DONE]":
                            continue
                        chunk = json.loads(raw_data)
                        delta = extract_stream_delta(chunk)
                        if delta:
                            collected.append(delta)
                            yield delta
        except Exception as exc:
            if trace is not None:
                trace.llm_response(
                    task_type=task_type,
                    model=model,
                    mock=False,
                    content="".join(collected),
                    error=_describe_exception(exc),
                )
            raise

        if trace is not None:
            trace.llm_response(
                task_type=task_type,
                model=model,
                mock=False,
                content="".join(collected),
            )
