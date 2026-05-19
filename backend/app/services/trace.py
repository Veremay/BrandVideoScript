"""Structured execution traces for brand pipeline, tools, and LLM calls."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.models.script import new_id, now_iso

logger = logging.getLogger("brandvideo.trace")

TRACE_KIND_BRIEF_UPLOADED = "brief_uploaded"
TRACE_KIND_PIPELINE_STARTED = "pipeline_started"
TRACE_KIND_PIPELINE_COMPLETED = "pipeline_completed"
TRACE_KIND_PIPELINE_FAILED = "pipeline_failed"
TRACE_KIND_TOOL_CALL = "tool_call"
TRACE_KIND_TOOL_RESULT = "tool_result"
TRACE_KIND_LLM_REQUEST = "llm_request"
TRACE_KIND_LLM_RESPONSE = "llm_response"

MAX_TRACE_EVENTS = 100
MAX_PREVIEW_CHARS = 600
MAX_RESPONSE_PREVIEW_CHARS = 1200


def _truncate(value: str, limit: int = MAX_PREVIEW_CHARS) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _message_summary(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role") or "unknown"
        content = str(msg.get("content") or "")
        summary.append({"role": role, "chars": len(content), "preview": _truncate(content, 200)})
    return summary


class TraceRecorder:
    """Collects trace events for one pipeline/chat run; merge into brand_research via merge_brand_research."""

    def __init__(
        self,
        *,
        source: str,
        run_id: str | None = None,
        initial_events: list[dict[str, Any]] | None = None,
    ) -> None:
        self.source = source
        self.run_id = run_id or new_id("run")
        self.events: list[dict[str, Any]] = list(initial_events or [])

    def record(self, kind: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "id": new_id("trace"),
            "ts": now_iso(),
            "kind": kind,
            "source": self.source,
            "run_id": self.run_id,
            "data": data or {},
        }
        self.events.append(event)
        if len(self.events) > MAX_TRACE_EVENTS:
            self.events = self.events[-MAX_TRACE_EVENTS:]
        logger.info("trace %s", json.dumps(event, ensure_ascii=False, default=str))
        return event

    def brief_uploaded(self, *, filename: str | None, text_length: int, summary: str) -> dict[str, Any]:
        return self.record(
            TRACE_KIND_BRIEF_UPLOADED,
            {
                "filename": filename,
                "text_length": text_length,
                "parse_status": "parsed",
                "summary_preview": _truncate(summary, 240),
            },
        )

    def pipeline_started(self) -> dict[str, Any]:
        return self.record(TRACE_KIND_PIPELINE_STARTED, {})

    def pipeline_completed(self, *, insight_count: int) -> dict[str, Any]:
        return self.record(TRACE_KIND_PIPELINE_COMPLETED, {"insight_count": insight_count})

    def pipeline_failed(self, *, error: str) -> dict[str, Any]:
        return self.record(TRACE_KIND_PIPELINE_FAILED, {"error": _truncate(error, 500)})

    def tool_call(self, tool: str, input_data: dict[str, Any]) -> dict[str, Any]:
        return self.record(TRACE_KIND_TOOL_CALL, {"tool": tool, "input": input_data})

    def tool_result(self, tool: str, output: Any, *, error: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"tool": tool, "output": output}
        if error:
            payload["error"] = _truncate(error, 500)
        return self.record(TRACE_KIND_TOOL_RESULT, payload)

    def llm_request(
        self,
        *,
        task_type: str,
        model: str,
        messages: list[dict[str, str]],
        stream: bool = False,
        mock: bool = False,
    ) -> dict[str, Any]:
        return self.record(
            TRACE_KIND_LLM_REQUEST,
            {
                "task_type": task_type,
                "model": model,
                "stream": stream,
                "mock": mock,
                "messages": _message_summary(messages),
            },
        )

    def llm_response(
        self,
        *,
        task_type: str,
        model: str,
        mock: bool,
        raw: dict[str, Any] | None = None,
        content: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        usage: dict[str, Any] = {}
        if raw and not mock:
            usage = raw.get("usage") or {}
        preview = _truncate(content or "", MAX_RESPONSE_PREVIEW_CHARS) if content else ""
        if not preview and raw and not mock:
            try:
                choices = raw.get("choices") or []
                message = choices[0].get("message") or {}
                preview = _truncate(str(message.get("content") or ""), MAX_RESPONSE_PREVIEW_CHARS)
            except (IndexError, KeyError, TypeError):
                preview = ""
        return self.record(
            TRACE_KIND_LLM_RESPONSE,
            {
                "task_type": task_type,
                "model": model,
                "mock": mock,
                "content_preview": preview,
                "usage": usage,
                "error": _truncate(error, 500) if error is not None else None,
            },
        )

    def merge_brand_research(self, brand_research: dict[str, Any]) -> dict[str, Any]:
        merged = {**brand_research, "trace_run_id": self.run_id, "traces": self.events[-MAX_TRACE_EVENTS:]}
        return merged
