# Phase 2 Agent Infrastructure Design

## Overview

Phase 2 builds the real Agent communication foundation for BrandVideo. The goal is to let any Agent stream a real SiliconFlow response through the backend, persist both user and assistant messages, and restore chat history after refresh.

This phase uses a backend SSE gateway. The frontend never calls SiliconFlow directly. The backend validates project ownership, loads editable prompt templates, builds context, calls SiliconFlow with `stream=true`, forwards tokens as SSE events, and saves the final assistant message.

Phase 2 does not implement BrandInsight generation, AudienceAnalysis generation, ExpertSuggestion generation, or hunk application. Those structured artifacts remain Phase 3, Phase 4, and Phase 5 work. Phase 2 reserves an `artifact` SSE event shape so later phases can add structured outputs without changing the streaming contract.

## Confirmed Decisions

- Use方案 A: backend SSE gateway plus real SiliconFlow streaming.
- Complete real end-to-end SiliconFlow integration in this phase.
- Keep mock behavior only as an explicit fallback for tests or local diagnostics, not as the acceptance path.
- Keep one editable `.md` prompt file per Agent.
- Do not cache prompt files in Phase 2, so manual prompt edits are picked up on the next request.
- Return clear SSE errors when prompt files or `SILICONFLOW_API_KEY` are missing.

## Backend Architecture

### Routes

Add `app/api/routes/agents.py`.

Endpoints:

- `POST /api/projects/{project_id}/agents/{agent_type}/stream`
- `GET /api/projects/{project_id}/agents/{agent_type}/messages?user_id=...&limit=...`

Valid `agent_type` values:

- `brand`
- `audience`
- `expert`

The stream endpoint returns `text/event-stream`.

SSE event types:

- `token`: partial assistant text
- `artifact`: reserved for later structured outputs
- `done`: stream completed and assistant message persisted
- `error`: user-visible failure

Example:

```text
event: token
data: {"content":"这段脚本"}

event: done
data: {"message_id":"msg_abc123"}
```

### Message Persistence

Add `app/repositories/agent_messages.py`.

Use the existing MongoDB database with a new `agent_messages` collection.

Message document:

```json
{
  "_id": "msg_abc123",
  "project_id": "project_abc123",
  "user_id": "user_001",
  "agent_type": "brand",
  "role": "user",
  "content": "帮我看看这段是否太像广告",
  "quotes": [
    {
      "text": "这款产品真的改变了我的生活",
      "row_id": "row_001",
      "column_id": "col_scene",
      "selection_start": 0,
      "selection_end": 12
    }
  ],
  "created_at": "2026-05-19T15:30:00"
}
```

Repository responsibilities:

- Create user messages.
- Create assistant messages.
- Return recent messages by `project_id`, `user_id`, `agent_type`, newest last.
- Enforce a bounded default history limit, initially 20 messages.

### Prompt Templates

Add prompt files:

- `backend/app/prompts/brand.md`
- `backend/app/prompts/audience.md`
- `backend/app/prompts/expert.md`

Add `app/services/prompt_loader.py`.

The loader reads the prompt file for the requested Agent on every stream request. It performs minimal variable replacement and raises a clear error if the file is missing or empty.

Supported variables:

- `{{brief_summary}}`
- `{{script_summary}}`
- `{{recent_messages}}`
- `{{quotes}}`
- `{{active_persona}}`
- `{{brand_insights}}`
- `{{audience_analysis}}`

The prompt file is the manual configuration entry point. Code should not hide fallback system prompts. If a prompt is invalid, the backend returns an `error` SSE event so the problem is visible during prompt iteration.

### Context Builder

Add `app/services/agent_context.py`.

Responsibilities:

- Load the current project.
- Build a compact script summary from `current_script.columns` and `current_script.rows`.
- Format quotes with row and column metadata.
- Format recent messages for the current Agent only.
- Inject existing structured project fields when useful:
  - Brand Agent may receive brief summary, script summary, quotes, recent brand messages.
  - Audience Agent may receive script summary, quotes, recent audience messages, active persona if available.
  - Expert Agent may receive script summary, brand insights, audience analysis, quotes, recent expert messages.

Agents do not read other Agents' raw chat history in Phase 2. Cross-Agent context flows through structured project fields only.

### LLM Client

Extend `app/services/llm_client.py`.

New capability:

- `stream_chat(...) -> AsyncIterator[str]`

Expected behavior:

- Select model through `ModelRouter`.
- Require `SILICONFLOW_API_KEY` for real streaming.
- Send OpenAI-compatible payload to `/chat/completions` with `stream=true`.
- Parse OpenAI-compatible streaming chunks.
- Yield content deltas only.
- Raise a clear error for upstream HTTP errors or malformed streams.

Task type mapping:

- Brand Agent user chat: `brand_chat`
- Audience Agent user chat: `audience_chat`
- Expert Agent user chat: `expert_chat`

These default to the lighter model unless complexity is marked high. Phase 2 can start with normal complexity for all user chat, while keeping the route open for later task-specific escalation.

### Streaming Service

Add `app/services/agent_stream.py`.

Flow:

1. Validate `project_id` and `user_id`.
2. Persist the user message.
3. Build Agent messages from prompt template plus recent conversation.
4. Call `LLMClient.stream_chat`.
5. Yield `token` events as upstream tokens arrive.
6. Accumulate assistant content.
7. Persist assistant message after completion.
8. Yield `done` with `message_id`.
9. On errors, yield `error`.

If assistant content is empty, do not save an assistant message. Return an `error` event.

## Frontend Architecture

### Types

Add types in `frontend/src/lib/types.ts`:

- `AgentMessage`
- `AgentQuote`
- `AgentStreamEvent`
- `AgentStreamPayload`

### API Client

Extend `frontend/src/lib/api.ts`.

Add:

- `fetchAgentMessages(projectId, userId, agentType)`
- `streamAgentMessage(projectId, userId, agentType, payload, handlers)`

The stream function uses `fetch` and reads `response.body.getReader()`. It parses SSE frames incrementally and calls handlers for `token`, `done`, and `error`.

### Store

Extend `frontend/src/store/appStore.ts`.

For each Agent keep:

- `messages`
- `streaming`
- `error`

Actions:

- Set loaded messages.
- Append user message optimistically.
- Start assistant placeholder.
- Append streamed token to placeholder.
- Mark stream done.
- Mark stream error.

### UI

Update `AgentChat` in `frontend/src/components/EditorShell.tsx`.

Behavior:

- On send, append user message immediately.
- Create an assistant placeholder.
- Stream tokens into the placeholder.
- Disable only the sending Agent input during streaming.
- Show a compact error state when stream fails.
- Load message history when a project opens or an Agent panel is opened.

The Brand Agent chat should no longer create a BrandInsight as its send action. It should send a real Agent message. BrandInsight CRUD remains available in the pinned insight area.

## Error Handling

- Missing `SILICONFLOW_API_KEY`: return `error` SSE with a clear environment configuration message.
- Missing or empty prompt file: return `error` SSE naming the prompt path.
- SiliconFlow HTTP failure: return `error` SSE with upstream status and concise message.
- Stream interruption: frontend preserves partial assistant text and shows retry affordance.
- Project not found: return normal HTTP 404 before starting the stream.
- Unsupported Agent type: return normal HTTP 422 or 400.
- Empty assistant response: return `error` SSE and do not persist assistant message.

## Testing Strategy

Backend TDD:

- Prompt loader reads each Agent prompt and replaces variables.
- Prompt loader rejects missing and empty prompt files.
- Agent message repository persists and returns recent messages in chronological order.
- SSE formatter emits valid `token`, `done`, and `error` frames.
- LLM stream parser extracts content deltas from OpenAI-compatible chunks.

Frontend verification:

- TypeScript typecheck passes.
- AgentChat can consume synthetic SSE frames in the client helper.
- Manual E2E with real `SILICONFLOW_API_KEY`:
  - Start MongoDB and Redis.
  - Start FastAPI.
  - Start Next.js.
  - Open a project.
  - Send a Brand Agent message.
  - Observe streamed tokens.
  - Refresh page and confirm persisted user and assistant messages reload.

## Acceptance Criteria

- `backend/app/prompts/brand.md`, `audience.md`, and `expert.md` exist and can be edited manually.
- Real SiliconFlow streaming works through the backend when `SILICONFLOW_API_KEY` is configured.
- The frontend displays tokens as they arrive.
- User and assistant messages are persisted in `agent_messages`.
- Message history reloads after refresh.
- The stream endpoint returns clear `error` SSE events for missing API key, missing prompt, and upstream failure.
- Brand Agent chat no longer writes BrandInsight as a fake chat response.
- Existing project, script, brief, and BrandInsight behavior remains intact.

## Out of Scope

- BrandInsight automatic JSON extraction from LLM output.
- AudienceAnalysis automatic JSON extraction.
- ExpertSuggestion and diff hunk generation.
- Redis stream replay or durable background job recovery.
- LangGraph orchestration.
- Multi-persona audience comparison.
- PDF/DOC/PPT brief parsing.
