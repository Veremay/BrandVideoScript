# Script Creation Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the workspace mode at project/script creation so each script is born as either system-assisted `full` or plain `vanilla`.

**Architecture:** Add `mode` to project creation request/response and store it on the project. Generate `current_script.settings` inside `default_script(mode)`. Frontend creation UI passes the mode and the editor reads from the active project instead of localStorage.

**Tech Stack:** FastAPI, Pydantic, Python unittest, Next.js, TypeScript, Zustand.

---

### Task 1: Backend Mode Creation

**Files:**
- Modify: `backend/app/models/script.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/repositories/projects.py`
- Test: `backend/tests/test_script_validate.py`

- [ ] **Step 1: Write failing tests for script settings**

Add tests asserting `default_script("full")` has `settings.mode == "full"` and `system_support_enabled is True`, while `default_script("vanilla")` has `settings.mode == "vanilla"` and `system_support_enabled is False`.

- [ ] **Step 2: Run the script validation test**

Run: `uv run python -m pytest tests/test_script_validate.py -q` from `backend`.
Expected: fail because `default_script` does not accept a mode argument.

- [ ] **Step 3: Implement script settings and project mode persistence**

Update `default_script(mode="full")`, `ProjectCreateRequest.mode`, `ProjectResponse.mode`, `serialize_project`, and `create_project(..., mode="full")`.

- [ ] **Step 4: Re-run backend tests**

Run: `uv run python -m pytest tests/test_script_validate.py -q` from `backend`.
Expected: pass.

### Task 2: Frontend Creation Wiring

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/store/appStore.ts`
- Modify: `frontend/src/components/CreateProjectDialog.tsx`
- Modify: `frontend/src/components/ProjectList.tsx`
- Modify: `frontend/src/components/EditorShell.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Add shared `AppMode` type to frontend project types**

Define `AppMode = "vanilla" | "full"` in `types.ts`, add `mode?: AppMode` to `Project`, and add `settings?: { mode?: AppMode; system_support_enabled?: boolean }` to `Script`.

- [ ] **Step 2: Pass mode from creation dialog to API**

Extend `CreateProjectPayload`, `createProject`, and `ProjectList.handleCreateConfirm` to include `mode`.

- [ ] **Step 3: Derive editor mode from project**

Remove persistent localStorage mode switching from Zustand, set app mode from `project.mode ?? project.current_script.settings.mode ?? "full"`, and remove mode switching controls from the settings menu.

- [ ] **Step 4: Verify frontend types**

Run: `npm run typecheck` from `frontend`.
Expected: pass.
