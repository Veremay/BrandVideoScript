# Phase 3 Brand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brief upload-only UX; automatic brand research (Tavily + llm-wiki) and explicit/implicit requirement analysis; Brand Agent context and pinned insights.

**Design spec (authoritative):** `docs/superpowers/specs/2026-05-19-phase-3-brand-agentic-search-design.md`

**Architecture:** Store `brief`, `brand_research`, and `brand_insights` on the MongoDB project document. `BrandBriefPipeline` runs after brief parse: agentic search → LLM structured analysis → persist insights. Brand chat/stream merges brief summary, research snippets, and insights into context.

**Tech Stack:** FastAPI, Motor/MongoDB, Pydantic, Tavily API, local `llm-wiki/` markdown, Next.js, React, Zustand, TypeScript, SiliconFlow.

---

### Task 1: Brief Upload UX (upload only)

**Files:**
- Modify: `frontend/src/components/EditorShell.tsx`

- [ ] Remove「粘贴 Brief」button and `window.prompt` paste flow.
- [ ] Keep「上传品牌 Brief」for `.md` / `.txt` only.
- [ ] Show parse + brand analysis status after upload (loading / done / failed).

### Task 2: Backend — `brand_research` + Brief pipeline shell

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/repositories/projects.py`
- Create: `backend/app/services/brand_research.py` (Tavily + wiki loader)
- Create: `backend/app/services/brand_brief_pipeline.py`
- Test: `backend/tests/test_brand_research.py`

- [ ] Add `brand_research` schema and repository helpers.
- [ ] Implement wiki match under `llm-wiki/brands/{slug}/`.
- [ ] Implement Tavily search wrapper with env-based enable/disable.
- [ ] On `POST /brief` success + `parse_status=parsed`, enqueue or await `BrandBriefPipeline`.

### Task 3: Backend — Brand data operations (existing + pipeline output)

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/repositories/projects.py`
- Modify: `backend/app/api/routes/projects.py`
- Test: `backend/tests/test_brand_ops.py`

- [ ] Repository helpers: `update_brief`, insight CRUD, pipeline result merge.
- [ ] Extend `evidence.source_type` with `web`, `brand_wiki`.
- [ ] `POST /agents/brand/analyze-brief` as manual re-run only.
- [ ] Auto pipeline writes `explicit_requirement` and `implicit_requirement` insights.

### Task 4: Brand Agent context + prompts

**Files:**
- Modify: `backend/app/services/brand_agent.py` (or equivalent)
- Modify: `backend/app/prompts/brand.md` (if present)

- [ ] Build context: `brief.summary`, `brand_research`, existing `brand_insights`, quotes, script rows.
- [ ] Initial analysis prompt requires evidence from brief / web / wiki.
- [ ] Stream SSE `artifact` with `brand_insights` updates.

### Task 5: llm-wiki bootstrap

**Files:**
- Create: `llm-wiki/README.md`
- Create: `llm-wiki/brands/_example/meta.json`, `handbook.md`

- [ ] Document slug/alias conventions.
- [ ] At least one sample brand for local dev.

### Task 6: Frontend — pinned binding + research visibility

**Files:**
- Modify: `frontend/src/lib/types.ts`, `api.ts`, `store/appStore.ts`, `EditorShell.tsx`, `globals.css`

- [ ] Types for `brand_research`, extended evidence sources.
- [ ] Pinned tabs consume pipeline-generated insights.
- [ ] Optional: collapsible「品牌检索依据」showing web/wiki snippets.

### Task 7: Verification and checklist

**Files:**
- Modify: `docs/development_plan_P0.md`

- [ ] Backend unit tests for research + pipeline (mock Tavily).
- [ ] Frontend typecheck.
- [ ] Update Phase 3 checklist per design spec §7.
