# Brand LLM-WiKi Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real LLM-WiKi-style brand knowledge layer for Brand Agent.

**Architecture:** Compile existing brand manuals into linked Markdown pages under `backend/data/brand_wiki/<brand>/`. Expose search/read/context helpers in `brand_wiki.py`, then inject curated Wiki context into Brand Agent requirement extraction.

**Tech Stack:** Python, pathlib, regex, pytest/unittest, existing backend service patterns.

---

### Task 1: Runtime Search And Read

**Files:**
- Modify: `backend/app/services/tools/brand_wiki.py`
- Test: `backend/tests/test_brand_wiki.py`

- [ ] **Step 1: Write failing tests**

Create tests for brand matching, page search, page read, task context, and fallback distilled lookup.

- [ ] **Step 2: Run the tests to verify failure**

Run: `uv run pytest backend/tests/test_brand_wiki.py -q`

Expected: FAIL because `brand_wiki_search`, `brand_wiki_read`, and `brand_wiki_context_for_task` do not exist.

- [ ] **Step 3: Implement runtime helpers**

Add Wiki directory constants, safe page parsing, brand matching, keyword ranking, read helpers, and curated task context assembly. Keep `brand_wiki_lookup` backward compatible.

- [ ] **Step 4: Run tests**

Run: `uv run pytest backend/tests/test_brand_wiki.py -q`

Expected: PASS.

### Task 2: Compile Script

**Files:**
- Modify: `backend/scripts/distill_brand_wiki.py`
- Test: `backend/tests/test_brand_wiki.py`

- [ ] **Step 1: Write failing compile test**

Add a test that compiles a temporary manual into `_index.md`, topic pages, and `error_book.yaml`.

- [ ] **Step 2: Run the test to verify failure**

Run: `uv run pytest backend/tests/test_brand_wiki.py -q`

Expected: FAIL because the compile function does not exist.

- [ ] **Step 3: Implement deterministic compiler**

Add `compile_manual_to_wiki` and keep the existing LLM distillation path intact. The deterministic compiler maps source text into standard pages with source notes and wikilinks.

- [ ] **Step 4: Run tests**

Run: `uv run pytest backend/tests/test_brand_wiki.py -q`

Expected: PASS.

### Task 3: Brand Agent Context

**Files:**
- Modify: `backend/app/services/agents/brand_agent.py`
- Test: `backend/tests/test_agent_prompts.py` or existing Brand Agent tests if more specific.

- [ ] **Step 1: Write or update test expectation**

Ensure requirement extraction reports `brand_wiki_search` and `brand_wiki_read` in `tool_calls_used` and uses curated Wiki context.

- [ ] **Step 2: Implement Brand Agent wiring**

Replace the direct full-text Wiki block with `brand_wiki_context_for_task`.

- [ ] **Step 3: Run targeted tests**

Run: `uv run pytest backend/tests/test_brand_wiki.py backend/tests/test_agent_prompts.py -q`

Expected: PASS.

### Task 4: Verification

- [ ] **Step 1: Run targeted backend suite**

Run: `uv run pytest backend/tests/test_brand_wiki.py backend/tests/test_agent_prompts.py backend/tests/test_coordinator.py -q`

Expected: PASS.

- [ ] **Step 2: Inspect diff**

Run: `git diff -- backend/app/services/tools/brand_wiki.py backend/scripts/distill_brand_wiki.py backend/app/services/agents/brand_agent.py backend/tests/test_brand_wiki.py docs/superpowers`

Expected: Diff only contains Brand LLM-WiKi work.
