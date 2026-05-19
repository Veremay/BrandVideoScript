# Phase 3 Brand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 3 brand-side MVP loop: save parsed Brief text and manage structured BrandInsight pinned items.

**Architecture:** Store Brief and BrandInsight data inside the existing MongoDB project document, matching the repository's current lightweight Project model. Add focused backend repository functions and project routes, then bind the existing brand pinned UI to `project.brand_insights`.

**Tech Stack:** FastAPI, Motor/MongoDB, Pydantic, Next.js, React, Zustand, TypeScript.

---

### Task 1: Backend Brand Data Operations

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/repositories/projects.py`
- Test: `backend/tests/test_brand_ops.py`

- [ ] Write failing unit tests for Brief parsing and BrandInsight CRUD helper behavior.
- [ ] Run `uv run python -m unittest backend.tests.test_brand_ops -v` and confirm the tests fail because helpers do not exist.
- [ ] Add request schemas and repository helpers for `update_brief`, `create_brand_insight`, `update_brand_insight`, and `delete_brand_insight`.
- [ ] Run `uv run python -m unittest backend.tests.test_brand_ops -v` and confirm the tests pass.

### Task 2: Backend API Routes

**Files:**
- Modify: `backend/app/api/routes/projects.py`
- Test: `backend/tests/test_brand_ops.py`

- [ ] Add route-level coverage for route helper importability where practical.
- [ ] Add project routes for `POST /brief`, `POST /agents/brand/insights`, `PATCH /agents/brand/insights/{insight_id}`, and `DELETE /agents/brand/insights/{insight_id}`.
- [ ] Preserve existing project-not-found and validation style.
- [ ] Run backend unit tests.

### Task 3: Frontend Brand Panel Binding

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/store/appStore.ts`
- Modify: `frontend/src/components/EditorShell.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] Add `Brief` and `BrandInsight` TypeScript types.
- [ ] Add API client functions for Brief and BrandInsight CRUD.
- [ ] Add store actions for active pinned tab, Brief save, and insight CRUD results.
- [ ] Replace static brand pinned content with editable, deletable, expandable insight objects grouped by category.
- [ ] Keep UI compact and consistent with the existing app shell.

### Task 4: Verification and Checklist

**Files:**
- Modify: `docs/development_plan_P0.md`

- [ ] Run backend unit tests.
- [ ] Run frontend typecheck.
- [ ] Update Phase 3 checklist items that are now implemented.
