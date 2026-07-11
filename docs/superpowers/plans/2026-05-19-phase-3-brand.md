# Phase 3 Brand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brief upload-only UX; automatic brand research (Tavily + llm-wiki) and explicit/implicit requirement analysis; Brand Agent context and pinned insights.

**Design spec (authoritative):** `docs/superpowers/specs/2026-05-19-phase-3-brand-agentic-search-design.md`

**Architecture:** Store `brief`, `brand_research`, and `brand_insights` on the MongoDB project document. `BrandBriefPipeline` runs after brief parse: agentic search → LLM structured analysis → persist insights. Brand chat/stream merges brief summary, research snippets, and insights into context.

**Tech Stack:** FastAPI, Motor/MongoDB, Pydantic, Tavily API, local `llm-wiki/` markdown, Next.js, React, Zustand, TypeScript, SiliconFlow.

---

### Task 1: Brief Upload UX

**Files:**
- Modify: `frontend/src/components/EditorShell.tsx`

- [x] Remove「粘贴 Brief」button and `window.prompt` paste flow.
- [x] Keep「上传品牌 Brief」for `.md` / `.txt` only.
- [x] Show parse + brand analysis status after upload (loading / done / failed).

### Task 2: Backend — `brand_research` + Brief pipeline shell

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/repositories/projects.py`
- Create: `backend/app/services/brand_wiki.py` (wiki loader)
- Create: `backend/app/services/tavily_search.py` (Tavily wrapper)
- Create: `backend/app/services/brand_brief_pipeline.py`
- Test: `backend/tests/test_brand_brief_pipeline.py`

- [x] Add `brand_research` schema and repository helpers.
- [x] Implement wiki match under `llm-wiki/brands/{slug}/`.
- [x] Implement Tavily search wrapper with env-based enable/disable.
- [x] On `POST /brief` success + `parse_status=parsed`, enqueue or await `BrandBriefPipeline`.

### Task 3: Backend — Brand data operations (existing + pipeline output)

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/repositories/projects.py`
- Modify: `backend/app/api/routes/projects.py`
- Test: `backend/tests/test_brand_ops.py`

- [x] Repository helpers: `update_brief`, insight CRUD, pipeline result merge.
- [x] Extend `evidence.source_type` with `web`, `brand_wiki`.
- [x] `POST /agents/brand/analyze-brief` as manual re-run only.
- [x] Auto pipeline writes `explicit_requirement` and `implicit_requirement` insights.

### Task 4: Brand Agent context + prompts

**Files:**
- Modify: `backend/app/services/agent_context.py`
- Modify: `backend/app/prompts/brand.md`

- [x] Build context: `brief.summary`, `brand_entity`, `brand_research`, structured `brand_insights`, quotes, script rows.
- [x] Initial analysis prompt requires evidence from brief / web / wiki.
- [x] Stream SSE `artifact` with `brand_insight_proposals` (Task 8).

### Task 5: llm-wiki bootstrap

**Files:**
- Create: `llm-wiki/README.md`
- Create: `llm-wiki/brands/_example/meta.json`, `handbook.md`

- [x] Document slug/alias conventions.
- [x] At least one sample brand for local dev.

### Task 6: Frontend — pinned binding + research visibility

**Files:**
- Modify: `frontend/src/lib/types.ts`, `api.ts`, `store/appStore.ts`, `EditorShell.tsx`, `globals.css`

- [x] Types for `brand_research`, extended evidence sources.
- [x] Pinned tabs consume pipeline-generated insights.
- [ ] Optional: collapsible「品牌检索依据」showing web/wiki snippets.

### Task 7: Verification and checklist

**Files:**
- Modify: `docs/development_plan_P0.md`

- [x] Backend unit tests for research + pipeline (mock Tavily). 55 tests passing.
- [x] Frontend typecheck.
- [ ] Update Phase 3 checklist per design spec §7.

### Task 8: Observability + agent-driven insight feedback loop (post-原计划补充)

**Files:**
- Create: `backend/app/services/trace.py`
- Create: `backend/app/services/brand_insight_proposals.py`
- Modify: `backend/app/services/llm_client.py`, `agent_stream.py`, `brand_brief_pipeline.py`
- Modify: `backend/app/prompts/brand.md`
- Modify: `frontend/src/lib/api.ts`, `EditorShell.tsx`
- Test: `backend/tests/test_trace.py`, `test_brand_insight_proposals.py`, `test_agent_stream.py`

- [x] Trace recorder: `brief_uploaded` / `pipeline_started|completed|failed` / `tool_call|tool_result` / `llm_request|llm_response`, persisted under `brand_research.traces`.
- [x] 8B brand entity extraction (`brand_extract_entity`) → `brand_research.entity` → drives multi-query Tavily (advanced depth, country=china, score >= 0.3).
- [x] Brand Agent emits `<brand_insight_proposals>` marker; backend strips & auto-creates `brand_insights` with `created_by="agent"`, `status="new"`. Tolerant to singular/plural & missing close tag.
- [x] SSE `artifact` + `done` events carry `proposal_count` / `persisted_count`; frontend refetches project and switches pinned tab on persistence.
- [x] LLM client uses configurable timeouts (`SILICONFLOW_CHAT_TIMEOUT=180`, `SILICONFLOW_STREAM_TIMEOUT=300`) and `_describe_exception` so traces don't swallow `ReadTimeout`.
