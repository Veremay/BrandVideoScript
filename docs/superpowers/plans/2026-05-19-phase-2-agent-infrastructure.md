# Phase 2 Agent Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build real SiliconFlow-backed Agent streaming with editable prompt `.md` files, persisted chat messages, and frontend token-by-token display.

**Architecture:** FastAPI exposes a project-scoped SSE Agent endpoint that persists user messages, loads an Agent prompt template, builds compact project context, streams SiliconFlow deltas, then persists the assistant message. Next.js reads the SSE response with `fetch`, updates per-Agent message state, and reloads persisted history after refresh.

**Tech Stack:** FastAPI, Motor/MongoDB, httpx, Pydantic, Next.js, React, TypeScript, Zustand, SiliconFlow OpenAI-compatible Chat Completions.

---

## File Structure

- Create: `backend/app/prompts/brand.md`
  - Editable Brand Agent system prompt template.
- Create: `backend/app/prompts/audience.md`
  - Editable Audience Agent system prompt template.
- Create: `backend/app/prompts/expert.md`
  - Editable Expert Agent system prompt template.
- Create: `backend/app/services/prompt_loader.py`
  - Reads Agent prompt templates and replaces context variables.
- Create: `backend/tests/test_prompt_loader.py`
  - Unit tests for prompt loading, variable replacement, and missing/empty prompt errors.
- Create: `backend/app/repositories/agent_messages.py`
  - Builds message documents and performs MongoDB persistence/query operations.
- Create: `backend/tests/test_agent_messages.py`
  - Unit tests for message document construction and recent-message ordering helpers.
- Create: `backend/app/services/sse.py`
  - Encodes SSE frames for `token`, `done`, and `error`.
- Create: `backend/tests/test_sse.py`
  - Unit tests for SSE frame encoding.
- Modify: `backend/app/services/llm_client.py`
  - Add real SiliconFlow async streaming support and stream chunk parsing.
- Create: `backend/tests/test_llm_streaming.py`
  - Unit tests for OpenAI-compatible streaming chunk parser and missing API key behavior.
- Create: `backend/app/services/agent_context.py`
  - Builds prompt messages for each Agent from project, prompt template, quotes, and recent history.
- Create: `backend/tests/test_agent_context.py`
  - Unit tests for script summary, quote formatting, and Agent-specific context inclusion.
- Create: `backend/app/services/agent_stream.py`
  - Orchestrates persistence, context construction, LLM streaming, SSE events, and final assistant save.
- Create: `backend/app/api/routes/agents.py`
  - Adds stream and history endpoints.
- Modify: `backend/app/api/routes/__init__.py`
  - Ensure the new route module can be imported.
- Modify: `backend/app/main.py`
  - Include `agents.router`.
- Modify: `backend/app/models/schemas.py`
  - Add Agent stream and message schemas.
- Modify: `frontend/src/lib/types.ts`
  - Add Agent message, quote, stream payload, and stream event types.
- Modify: `frontend/src/lib/api.ts`
  - Add message history fetch and SSE stream reader.
- Modify: `frontend/src/store/appStore.ts`
  - Add per-Agent messages, streaming state, error state, and streaming mutation actions.
- Modify: `frontend/src/components/EditorShell.tsx`
  - Replace mock chat send behavior with real streaming Agent chat and history loading.

---

### Task 1: Prompt Templates And Loader

**Files:**
- Create: `backend/app/prompts/brand.md`
- Create: `backend/app/prompts/audience.md`
- Create: `backend/app/prompts/expert.md`
- Create: `backend/app/services/prompt_loader.py`
- Test: `backend/tests/test_prompt_loader.py`

- [ ] **Step 1: Write failing tests for prompt loading and rendering**

```python
import tempfile
import unittest
from pathlib import Path

from app.services.prompt_loader import PromptLoader, PromptTemplateError


class PromptLoaderTest(unittest.TestCase):
    def test_renders_agent_prompt_with_context_variables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir)
            (prompts_dir / "brand.md").write_text(
                "Brand prompt\nBrief: {{brief_summary}}\nScript: {{script_summary}}",
                encoding="utf-8",
            )

            loader = PromptLoader(prompts_dir=prompts_dir)

            rendered = loader.render(
                "brand",
                {"brief_summary": "Launch brief", "script_summary": "3 rows"},
            )

            self.assertIn("Brand prompt", rendered)
            self.assertIn("Brief: Launch brief", rendered)
            self.assertIn("Script: 3 rows", rendered)

    def test_rejects_missing_prompt_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = PromptLoader(prompts_dir=Path(temp_dir))

            with self.assertRaisesRegex(PromptTemplateError, "Prompt file not found"):
                loader.render("brand", {})

    def test_rejects_empty_prompt_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir)
            (prompts_dir / "audience.md").write_text("   ", encoding="utf-8")
            loader = PromptLoader(prompts_dir=prompts_dir)

            with self.assertRaisesRegex(PromptTemplateError, "Prompt file is empty"):
                loader.render("audience", {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest backend.tests.test_prompt_loader -v`

Expected: FAIL with `ModuleNotFoundError` for `app.services.prompt_loader`.

- [ ] **Step 3: Implement prompt loader and prompt files**

```python
from pathlib import Path


AGENT_PROMPT_FILES = {
    "brand": "brand.md",
    "audience": "audience.md",
    "expert": "expert.md",
}


class PromptTemplateError(RuntimeError):
    pass


class PromptLoader:
    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir = prompts_dir or Path(__file__).resolve().parents[1] / "prompts"

    def render(self, agent_type: str, variables: dict[str, str]) -> str:
        filename = AGENT_PROMPT_FILES.get(agent_type)
        if filename is None:
            raise PromptTemplateError(f"Unsupported agent type: {agent_type}")

        path = self.prompts_dir / filename
        if not path.exists():
            raise PromptTemplateError(f"Prompt file not found: {path}")

        template = path.read_text(encoding="utf-8").strip()
        if not template:
            raise PromptTemplateError(f"Prompt file is empty: {path}")

        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered
```

Create prompt files with these contents:

```md
你是品牌合作视频脚本顾问中的品牌方 Agent。请从品牌安全、卖点表达、brief 一致性和合作方审片风险角度给出具体反馈。

## 当前 Brief 摘要
{{brief_summary}}

## 当前脚本摘要
{{script_summary}}

## 用户引用
{{quotes}}

## 最近对话
{{recent_messages}}
```

```md
你是品牌合作视频脚本顾问中的观众 Agent。请模拟目标观众，判断内容是否自然、可信、有趣，以及广告感是否过强。

## 当前 Persona
{{active_persona}}

## 当前脚本摘要
{{script_summary}}

## 用户引用
{{quotes}}

## 最近对话
{{recent_messages}}
```

```md
你是品牌合作视频脚本顾问中的专家 Agent。请综合品牌要求、观众反馈和创作者表达，给出可执行的修改建议。

## 品牌洞察
{{brand_insights}}

## 观众分析
{{audience_analysis}}

## 当前脚本摘要
{{script_summary}}

## 用户引用
{{quotes}}

## 最近对话
{{recent_messages}}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest backend.tests.test_prompt_loader -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompts backend/app/services/prompt_loader.py backend/tests/test_prompt_loader.py
git commit -m "feat: add editable agent prompt templates"
```

### Task 2: Agent Message Models And Repository Helpers

**Files:**
- Create: `backend/app/repositories/agent_messages.py`
- Test: `backend/tests/test_agent_messages.py`

- [ ] **Step 1: Write failing tests for message construction and ordering**

```python
import unittest

from app.repositories.agent_messages import build_agent_message, serialize_agent_message, sort_recent_messages


class AgentMessagesTest(unittest.TestCase):
    def test_build_agent_message_sets_metadata(self):
        message = build_agent_message(
            project_id="project_1",
            user_id="user_1",
            agent_type="brand",
            role="user",
            content="Is this too ad-like?",
            quotes=[{"text": "Buy now", "row_id": "row_1", "column_id": "col_scene"}],
        )

        self.assertTrue(message["_id"].startswith("msg_"))
        self.assertEqual(message["project_id"], "project_1")
        self.assertEqual(message["agent_type"], "brand")
        self.assertEqual(message["role"], "user")
        self.assertEqual(message["content"], "Is this too ad-like?")
        self.assertEqual(message["quotes"][0]["text"], "Buy now")
        self.assertIsNotNone(message["created_at"])

    def test_serialize_agent_message_uses_string_id(self):
        message = build_agent_message(
            project_id="project_1",
            user_id="user_1",
            agent_type="audience",
            role="assistant",
            content="It feels natural.",
            quotes=[],
        )

        serialized = serialize_agent_message(message)

        self.assertEqual(serialized["_id"], message["_id"])

    def test_sort_recent_messages_returns_chronological_order(self):
        messages = [
            {"_id": "msg_2", "created_at": "2026-05-19T10:00:02"},
            {"_id": "msg_1", "created_at": "2026-05-19T10:00:01"},
        ]

        ordered = sort_recent_messages(messages)

        self.assertEqual([message["_id"] for message in ordered], ["msg_1", "msg_2"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest backend.tests.test_agent_messages -v`

Expected: FAIL with `ModuleNotFoundError` for `app.repositories.agent_messages`.

- [ ] **Step 3: Implement repository helpers and async operations**

```python
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import new_id, now_iso


VALID_AGENT_TYPES = {"brand", "audience", "expert"}
VALID_ROLES = {"user", "assistant", "system"}


def build_agent_message(
    *,
    project_id: str,
    user_id: str,
    agent_type: str,
    role: str,
    content: str,
    quotes: list[dict],
) -> dict:
    if agent_type not in VALID_AGENT_TYPES:
        raise ValueError("Invalid agent type")
    if role not in VALID_ROLES:
        raise ValueError("Invalid message role")
    if not content.strip():
        raise ValueError("Message content cannot be empty")

    return {
        "_id": new_id("msg"),
        "project_id": project_id,
        "user_id": user_id,
        "agent_type": agent_type,
        "role": role,
        "content": content.strip(),
        "quotes": quotes,
        "created_at": now_iso(),
    }


def serialize_agent_message(document: dict) -> dict:
    document["_id"] = str(document["_id"])
    return document


def sort_recent_messages(messages: list[dict]) -> list[dict]:
    return sorted(messages, key=lambda message: message.get("created_at", ""))


async def create_agent_message(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    agent_type: str,
    role: str,
    content: str,
    quotes: list[dict],
) -> dict:
    message = build_agent_message(
        project_id=project_id,
        user_id=user_id,
        agent_type=agent_type,
        role=role,
        content=content,
        quotes=quotes,
    )
    await db.agent_messages.insert_one(message)
    return serialize_agent_message(message)


async def list_agent_messages(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    agent_type: str,
    limit: int = 20,
) -> list[dict]:
    cursor = (
        db.agent_messages.find({"project_id": project_id, "user_id": user_id, "agent_type": agent_type})
        .sort("created_at", -1)
        .limit(limit)
    )
    newest_first = [serialize_agent_message(message) async for message in cursor]
    return sort_recent_messages(newest_first)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest backend.tests.test_agent_messages -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/agent_messages.py backend/tests/test_agent_messages.py
git commit -m "feat: add agent message persistence helpers"
```

### Task 3: SSE Encoding And LLM Streaming Parser

**Files:**
- Create: `backend/app/services/sse.py`
- Modify: `backend/app/services/llm_client.py`
- Test: `backend/tests/test_sse.py`
- Test: `backend/tests/test_llm_streaming.py`

- [ ] **Step 1: Write failing SSE encoder tests**

```python
import json
import unittest

from app.services.sse import encode_sse


class SSETest(unittest.TestCase):
    def test_encode_sse_writes_event_and_json_data(self):
        frame = encode_sse("token", {"content": "hello"})

        self.assertEqual(frame, 'event: token\ndata: {"content":"hello"}\n\n')

    def test_encode_sse_escapes_newlines_inside_json(self):
        frame = encode_sse("error", {"message": "line 1\nline 2"})
        payload = frame.split("data: ", 1)[1].strip()

        self.assertEqual(json.loads(payload), {"message": "line 1\nline 2"})
```

- [ ] **Step 2: Write failing LLM chunk parser tests**

```python
import unittest

from app.services.llm_client import extract_stream_delta


class LLMStreamingTest(unittest.TestCase):
    def test_extract_stream_delta_reads_openai_compatible_content(self):
        chunk = {
            "choices": [
                {
                    "delta": {
                        "content": "hello"
                    }
                }
            ]
        }

        self.assertEqual(extract_stream_delta(chunk), "hello")

    def test_extract_stream_delta_ignores_empty_delta(self):
        self.assertEqual(extract_stream_delta({"choices": [{"delta": {}}]}), "")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run python -m unittest backend.tests.test_sse backend.tests.test_llm_streaming -v`

Expected: FAIL because `app.services.sse` and `extract_stream_delta` do not exist.

- [ ] **Step 4: Implement SSE encoder and stream parser**

```python
import json
from typing import Any


def encode_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"
```

Add to `llm_client.py`:

```python
from collections.abc import AsyncIterator
import json


class LLMConfigurationError(RuntimeError):
    pass


def extract_stream_delta(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    return delta.get("content") or ""
```

Add `LLMClient.stream_chat`:

```python
    async def stream_chat(
        self,
        *,
        messages: list[dict[str, str]],
        task_type: str,
        response_format: dict[str, Any] | None = None,
        complexity: str = "normal",
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

        async with httpx.AsyncClient(base_url=self.settings.siliconflow_base_url, timeout=60) as client:
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
                        yield delta
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run python -m unittest backend.tests.test_sse backend.tests.test_llm_streaming -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/sse.py backend/app/services/llm_client.py backend/tests/test_sse.py backend/tests/test_llm_streaming.py
git commit -m "feat: add llm streaming primitives"
```

### Task 4: Agent Context Builder

**Files:**
- Create: `backend/app/services/agent_context.py`
- Test: `backend/tests/test_agent_context.py`

- [ ] **Step 1: Write failing tests for context formatting**

```python
import unittest

from app.services.agent_context import build_agent_chat_messages, summarize_script


class AgentContextTest(unittest.TestCase):
    def test_summarize_script_includes_rows_and_columns(self):
        script = {
            "columns": [
                {"column_id": "col_duration", "label": "Duration"},
                {"column_id": "col_scene", "label": "Scene"},
            ],
            "rows": [
                {
                    "row_id": "row_1",
                    "cells": [
                        {"column_id": "col_duration", "value": "0-5"},
                        {"column_id": "col_scene", "value": "Opening shot"},
                    ],
                }
            ],
        }

        summary = summarize_script(script)

        self.assertIn("row_1", summary)
        self.assertIn("Duration: 0-5", summary)
        self.assertIn("Scene: Opening shot", summary)

    def test_build_agent_chat_messages_adds_system_history_and_user_message(self):
        project = {
            "brief": {"summary": "Launch brief"},
            "current_script": {"columns": [], "rows": []},
            "brand_insights": [],
            "audience_analysis": {},
            "personas": [],
            "active_persona_id": None,
        }

        messages = build_agent_chat_messages(
            agent_type="brand",
            system_prompt="System prompt",
            project=project,
            recent_messages=[{"role": "assistant", "content": "Earlier answer"}],
            user_message="New question",
            quotes=[{"text": "Selected quote"}],
        )

        self.assertEqual(messages[0], {"role": "system", "content": "System prompt"})
        self.assertEqual(messages[1], {"role": "assistant", "content": "Earlier answer"})
        self.assertEqual(messages[2]["role"], "user")
        self.assertIn("Selected quote", messages[2]["content"])
        self.assertIn("New question", messages[2]["content"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest backend.tests.test_agent_context -v`

Expected: FAIL with `ModuleNotFoundError` for `app.services.agent_context`.

- [ ] **Step 3: Implement context builder**

```python
from typing import Any


def summarize_script(script: dict[str, Any], max_rows: int = 12) -> str:
    columns = {column.get("column_id"): column.get("label", column.get("column_id", "")) for column in script.get("columns", [])}
    lines: list[str] = []
    for row in script.get("rows", [])[:max_rows]:
        cell_parts = []
        for cell in row.get("cells", []):
            label = columns.get(cell.get("column_id"), cell.get("column_id", ""))
            value = str(cell.get("value", "")).strip()
            if value:
                cell_parts.append(f"{label}: {value}")
        if cell_parts:
            lines.append(f"{row.get('row_id')}: " + " | ".join(cell_parts))
    return "\n".join(lines) if lines else "当前脚本为空。"


def format_quotes(quotes: list[dict[str, Any]]) -> str:
    if not quotes:
        return "无。"
    lines = []
    for quote in quotes:
        location = " / ".join(str(quote.get(key, "")) for key in ["row_id", "column_id"] if quote.get(key))
        prefix = f"[{location}] " if location else ""
        lines.append(f"- {prefix}{quote.get('text', '')}")
    return "\n".join(lines)


def format_recent_messages(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "无。"
    return "\n".join(f"{message.get('role')}: {message.get('content')}" for message in messages)


def find_active_persona(project: dict[str, Any]) -> str:
    active_id = project.get("active_persona_id")
    for persona in project.get("personas", []):
        if persona.get("persona_id") == active_id:
            return str(persona)
    return "未选择 persona。"


def build_prompt_variables(project: dict[str, Any], recent_messages: list[dict[str, Any]], quotes: list[dict[str, Any]]) -> dict[str, str]:
    return {
        "brief_summary": project.get("brief", {}).get("summary") or "无。",
        "script_summary": summarize_script(project.get("current_script", {})),
        "recent_messages": format_recent_messages(recent_messages),
        "quotes": format_quotes(quotes),
        "active_persona": find_active_persona(project),
        "brand_insights": str(project.get("brand_insights") or []),
        "audience_analysis": str(project.get("audience_analysis") or {}),
    }


def build_agent_chat_messages(
    *,
    agent_type: str,
    system_prompt: str,
    project: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    user_message: str,
    quotes: list[dict[str, Any]],
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]
    for message in recent_messages:
        role = message.get("role")
        if role in {"user", "assistant"} and message.get("content"):
            messages.append({"role": role, "content": message["content"]})
    quote_block = format_quotes(quotes)
    messages.append({"role": "user", "content": f"用户引用：\n{quote_block}\n\n用户问题：\n{user_message}"})
    return messages
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest backend.tests.test_agent_context -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_context.py backend/tests/test_agent_context.py
git commit -m "feat: build agent prompt context"
```

### Task 5: Agent Stream Route

**Files:**
- Create: `backend/app/services/agent_stream.py`
- Create: `backend/app/api/routes/agents.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/schemas.py`

- [ ] **Step 1: Add schemas**

Add to `schemas.py`:

```python
class AgentQuoteRequest(BaseModel):
    text: str = Field(min_length=1)
    row_id: str | None = None
    column_id: str | None = None
    selection_start: int | None = None
    selection_end: int | None = None


class AgentStreamRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1)
    quotes: list[AgentQuoteRequest] = Field(default_factory=list)


class AgentMessageResponse(BaseModel):
    id: str = Field(alias="_id")
    project_id: str
    user_id: str
    agent_type: Literal["brand", "audience", "expert"]
    role: Literal["user", "assistant", "system"]
    content: str
    quotes: list[dict[str, Any]]
    created_at: str


class AgentMessagesResponse(BaseModel):
    messages: list[AgentMessageResponse]
```

- [ ] **Step 2: Implement stream service**

```python
from collections.abc import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.agent_messages import create_agent_message, list_agent_messages
from app.repositories.projects import get_project
from app.services.agent_context import build_agent_chat_messages, build_prompt_variables
from app.services.llm_client import LLMClient
from app.services.prompt_loader import PromptLoader
from app.services.sse import encode_sse


TASK_TYPES = {
    "brand": "brand_chat",
    "audience": "audience_chat",
    "expert": "expert_chat",
}


async def stream_agent_response(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    agent_type: str,
    content: str,
    quotes: list[dict],
) -> AsyncIterator[str]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        yield encode_sse("error", {"message": "Project not found"})
        return

    await create_agent_message(
        db,
        project_id=project_id,
        user_id=user_id,
        agent_type=agent_type,
        role="user",
        content=content,
        quotes=quotes,
    )
    recent_messages = await list_agent_messages(db, project_id=project_id, user_id=user_id, agent_type=agent_type, limit=20)
    variables = build_prompt_variables(project, recent_messages, quotes)
    system_prompt = PromptLoader().render(agent_type, variables)
    llm_messages = build_agent_chat_messages(
        agent_type=agent_type,
        system_prompt=system_prompt,
        project=project,
        recent_messages=recent_messages[:-1],
        user_message=content,
        quotes=quotes,
    )

    assistant_parts: list[str] = []
    try:
        async for token in LLMClient().stream_chat(messages=llm_messages, task_type=TASK_TYPES[agent_type]):
            assistant_parts.append(token)
            yield encode_sse("token", {"content": token})
    except Exception as exc:
        yield encode_sse("error", {"message": str(exc)})
        return

    assistant_content = "".join(assistant_parts).strip()
    if not assistant_content:
        yield encode_sse("error", {"message": "Assistant response was empty"})
        return

    assistant = await create_agent_message(
        db,
        project_id=project_id,
        user_id=user_id,
        agent_type=agent_type,
        role="assistant",
        content=assistant_content,
        quotes=[],
    )
    yield encode_sse("done", {"message_id": assistant["_id"]})
```

- [ ] **Step 3: Implement route and register router**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import database_dependency
from app.models.schemas import AgentMessagesResponse, AgentStreamRequest
from app.repositories.agent_messages import list_agent_messages
from app.repositories.projects import get_project
from app.services.agent_stream import stream_agent_response

router = APIRouter(prefix="/projects/{project_id}/agents", tags=["agents"])


@router.get("/{agent_type}/messages", response_model=AgentMessagesResponse)
async def get_agent_messages(
    project_id: str,
    agent_type: str,
    user_id: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> dict:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"messages": await list_agent_messages(db, project_id=project_id, user_id=user_id, agent_type=agent_type, limit=limit)}


@router.post("/{agent_type}/stream")
async def stream_agent(
    project_id: str,
    agent_type: str,
    payload: AgentStreamRequest,
    db: AsyncIOMotorDatabase = Depends(database_dependency),
) -> StreamingResponse:
    return StreamingResponse(
        stream_agent_response(
            db,
            project_id=project_id,
            user_id=payload.user_id.strip(),
            agent_type=agent_type,
            content=payload.content,
            quotes=[quote.model_dump(exclude_none=True) for quote in payload.quotes],
        ),
        media_type="text/event-stream",
    )
```

Update `main.py`:

```python
from app.api.routes import agents, health, llm, projects, users
...
app.include_router(agents.router, prefix=settings.api_prefix)
```

- [ ] **Step 4: Run backend unit tests**

Run: `uv run python -m unittest discover -s backend/tests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_stream.py backend/app/api/routes/agents.py backend/app/main.py backend/app/models/schemas.py
git commit -m "feat: expose agent streaming routes"
```

### Task 6: Frontend Types And API Streaming Client

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add frontend types**

```ts
export type AgentQuote = {
  text: string;
  row_id?: string;
  column_id?: string;
  selection_start?: number;
  selection_end?: number;
};

export type AgentMessage = {
  _id: string;
  project_id: string;
  user_id: string;
  agent_type: AgentType;
  role: "user" | "assistant" | "system";
  content: string;
  quotes: AgentQuote[];
  created_at: string;
};

export type AgentStreamPayload = {
  user_id: string;
  content: string;
  quotes: AgentQuote[];
};
```

- [ ] **Step 2: Add API helpers**

```ts
export async function fetchAgentMessages(projectId: string, userId: string, agentType: AgentType): Promise<AgentMessage[]> {
  const data = await request<{ messages: AgentMessage[] }>(
    `/projects/${projectId}/agents/${agentType}/messages?user_id=${encodeURIComponent(userId)}`
  );
  return data.messages;
}

type StreamHandlers = {
  onToken: (content: string) => void;
  onDone: (messageId: string) => void;
  onError: (message: string) => void;
};

export async function streamAgentMessage(
  projectId: string,
  agentType: AgentType,
  payload: AgentStreamPayload,
  handlers: StreamHandlers
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/agents/${agentType}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok || !response.body) {
    handlers.onError(await response.text());
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const event = frame.match(/^event: (.+)$/m)?.[1];
      const data = frame.match(/^data: (.+)$/m)?.[1];
      if (!event || !data) continue;
      const parsed = JSON.parse(data);
      if (event === "token") handlers.onToken(parsed.content ?? "");
      if (event === "done") handlers.onDone(parsed.message_id ?? "");
      if (event === "error") handlers.onError(parsed.message ?? "Agent stream failed");
    }
  }
}
```

- [ ] **Step 3: Run frontend typecheck to reveal integration gaps**

Run: `npm run typecheck`

Expected: FAIL if imports are incomplete; otherwise PASS.

- [ ] **Step 4: Fix imports and type errors**

Ensure `api.ts` imports `AgentMessage`, `AgentStreamPayload`, and `AgentType`.

- [ ] **Step 5: Run frontend typecheck**

Run: `npm run typecheck`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat: add frontend agent stream client"
```

### Task 7: Frontend Store And AgentChat UI

**Files:**
- Modify: `frontend/src/store/appStore.ts`
- Modify: `frontend/src/components/EditorShell.tsx`

- [ ] **Step 1: Extend Zustand state**

Add per-Agent chat state:

```ts
type AgentChatState = {
  messages: AgentMessage[];
  streaming: boolean;
  error?: string;
};

type AppState = {
  ...
  agentChats: Record<AgentType, AgentChatState>;
  setAgentMessages: (agent: AgentType, messages: AgentMessage[]) => void;
  appendAgentMessage: (agent: AgentType, message: AgentMessage) => void;
  startAssistantMessage: (agent: AgentType, message: AgentMessage) => void;
  appendAssistantToken: (agent: AgentType, messageId: string, token: string) => void;
  setAgentStreaming: (agent: AgentType, streaming: boolean) => void;
  setAgentError: (agent: AgentType, error?: string) => void;
};
```

- [ ] **Step 2: Replace AgentChat mock send**

In `AgentChat`, import `fetchAgentMessages` and `streamAgentMessage`.

On mount or project/agent change:

```ts
useEffect(() => {
  if (!project) return;
  fetchAgentMessages(project._id, project.user_id, agent)
    .then((messages) => setAgentMessages(agent, messages))
    .catch((error) => setAgentError(agent, String(error)));
}, [agent, project, setAgentError, setAgentMessages]);
```

On send:

```ts
const optimisticUserMessage: AgentMessage = {
  _id: `local_user_${Date.now()}`,
  project_id: project._id,
  user_id: project.user_id,
  agent_type: agent,
  role: "user",
  content: message.trim(),
  quotes,
  created_at: new Date().toISOString()
};
const assistantId = `local_assistant_${Date.now()}`;
const optimisticAssistantMessage: AgentMessage = {
  _id: assistantId,
  project_id: project._id,
  user_id: project.user_id,
  agent_type: agent,
  role: "assistant",
  content: "",
  quotes: [],
  created_at: new Date().toISOString()
};
appendAgentMessage(agent, optimisticUserMessage);
startAssistantMessage(agent, optimisticAssistantMessage);
setAgentStreaming(agent, true);
setAgentError(agent, undefined);
await streamAgentMessage(
  project._id,
  agent,
  { user_id: project.user_id, content: optimisticUserMessage.content, quotes },
  {
    onToken: (token) => appendAssistantToken(agent, assistantId, token),
    onDone: async () => {
      setAgentStreaming(agent, false);
      setAgentMessages(agent, await fetchAgentMessages(project._id, project.user_id, agent));
    },
    onError: (error) => {
      setAgentStreaming(agent, false);
      setAgentError(agent, error);
    }
  }
);
```

- [ ] **Step 3: Render persisted messages**

Replace the static welcome-only chat area with:

```tsx
<div className="chat-area">
  {chat.messages.length ? (
    chat.messages.map((item) => (
      <div className={`msg ${item.role === "user" ? "msg-user" : "msg-agent"}`} key={item._id}>
        {item.content || "生成中..."}
      </div>
    ))
  ) : (
    <div className="msg msg-agent">{welcomeText(agent)}</div>
  )}
</div>
```

Disable send button while `chat.streaming` is true.

- [ ] **Step 4: Run frontend typecheck**

Run: `npm run typecheck`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/appStore.ts frontend/src/components/EditorShell.tsx
git commit -m "feat: stream agent chat in frontend"
```

### Task 8: Verification And Real E2E

**Files:**
- Modify only if verification exposes defects.

- [ ] **Step 1: Run backend tests**

Run: `uv run python -m unittest discover -s backend/tests -v`

Expected: PASS.

- [ ] **Step 2: Run frontend typecheck**

Run: `npm run typecheck`

Expected: PASS.

- [ ] **Step 3: Start dependencies**

Run: `docker compose up -d`

Expected: MongoDB and Redis containers start.

- [ ] **Step 4: Start backend**

Run: `uv run uvicorn app.main:app --reload`

Expected: backend serves `http://localhost:8000/api/health`.

- [ ] **Step 5: Start frontend**

Run: `npm run dev`

Expected: frontend serves `http://localhost:3000`.

- [ ] **Step 6: Real SiliconFlow manual E2E**

Prerequisite: `backend/.env` contains `SILICONFLOW_API_KEY`.

Manual flow:

1. Open `http://localhost:3000`.
2. Enter a `user_id`.
3. Create or open a project.
4. Open Brand Agent.
5. Send `请从品牌方角度看这段脚本是否有风险。`
6. Confirm tokens stream into the assistant message.
7. Refresh the page.
8. Confirm user and assistant messages reload from MongoDB.

Expected: real streamed assistant response appears and persists.

- [ ] **Step 7: Commit verification fixes if needed**

```bash
git add <changed-files>
git commit -m "fix: stabilize phase 2 agent streaming"
```
