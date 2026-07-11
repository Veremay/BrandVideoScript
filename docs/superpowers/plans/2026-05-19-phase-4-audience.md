# Phase 4 Audience Agent + Persona Implementation Plan

> **Design spec (authoritative):** `docs/superpowers/specs/2026-05-19-phase-4-audience-persona-design.md`

**Goal:** Persona CRUD with active selection; Audience Agent stream that emits structured `audience_analysis`; persona changes propagate stale flags.

**Architecture:** Store `personas[]`, `active_persona_id`, and `audience_analysis` on the MongoDB project document. The audience stream reuses the existing SSE plumbing and adds an `<audience_analysis>` artifact protocol parsed server-side.

**Tech Stack:** FastAPI, Motor/MongoDB, Pydantic, Next.js, React, Zustand, TypeScript, SiliconFlow (Qwen3-32B for analysis).

---

### Task 1: Backend — Persona + AudienceAnalysis data layer

**Files:**
- Modify: `backend/app/repositories/projects.py`
- Modify: `backend/app/models/schemas.py`
- Test: `backend/tests/test_persona_ops.py`

- [x] `build_persona`, `update_persona_in_list`, `remove_persona_from_list` helpers with validation (`ad_sensitivity` enum; lists default to `[]`).
- [x] `create_persona`, `update_persona`, `delete_persona`, `set_active_persona` async ops that flip `stale.audience` + `stale.expert` via `_write_personas`.
- [x] `save_audience_analysis` helper flips `stale.audience=false`, `stale.expert=true`.
- [x] Pydantic request models: `PersonaCreateRequest`, `PersonaUpdateRequest`, `ActivePersonaUpdateRequest`.

### Task 2: Backend — Persona routes

**Files:**
- Modify: `backend/app/api/routes/projects.py`

- [x] `POST   /projects/{id}/personas`
- [x] `PATCH  /projects/{id}/personas/{persona_id}`
- [x] `DELETE /projects/{id}/personas/{persona_id}`
- [x] `PATCH  /projects/{id}/active-persona`

### Task 3: Backend — Audience Agent prompt + context

**Files:**
- Modify: `backend/app/prompts/audience.md`
- Modify: `backend/app/services/agent_context.py`

- [x] Expand prompt: persona detail block, script summary, existing analysis baseline, response format rules (lead with persona name), `<audience_analysis>` artifact protocol.
- [x] `format_active_persona` renders the structured persona block instead of `str(dict)`.
- [x] `format_audience_analysis_existing` summarises latest analysis when present (or placeholder when not).
- [x] `build_prompt_variables` exposes new vars (`active_persona`, `audience_analysis_existing`, `persona_name`).

### Task 4: Backend — Audience analysis artifact parser

**Files:**
- Create: `backend/app/services/audience_analysis_proposals.py`
- Test: `backend/tests/test_audience_analysis_proposals.py`

- [x] Mirror `brand_insight_proposals` API: `MARKER_START/END`, `MAX_MARKER_LEN`, `find_marker_start`, `strip_proposal_block`, `parse_analysis_payload`.
- [x] Validate scores 1-5 integers; drop unknown row_ids; cap list lengths.
- [x] Return `None` (no artifact) vs `dict` (validated analysis) so caller can persist conditionally.

### Task 5: Backend — agent_stream audience branch

**Files:**
- Modify: `backend/app/services/agent_stream.py`
- Modify: `backend/app/repositories/projects.py` (`save_audience_analysis`)
- Test: `backend/tests/test_agent_stream.py` (audience cases)

- [x] Pre-flight guard: if `agent_type == "audience"` and no active persona, emit `error` event and stop.
- [x] `_HOLD_TAIL` uses the larger of `brand_marker.MAX_MARKER_LEN` and `audience_marker.MAX_MARKER_LEN`.
- [x] For audience: parse `<audience_analysis>` block, persist via `save_audience_analysis`, emit `event: artifact { type: "audience_analysis", analysis, persona_id, persona_name, persisted }`.
- [x] `event: done` carries `analysis_persisted` boolean.

### Task 6: Frontend — Types + API

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [x] `Persona`, `AudienceAnalysis`, `AudienceAnalysisPart` types matching spec.
- [x] Extend `Project` to use `Persona[]` and structured `AudienceAnalysis`.
- [x] API helpers: `createPersona`, `updatePersona`, `deletePersona`, `setActivePersona`.
- [x] Extend `AgentStreamArtifact` union to include `{ type: "audience_analysis", analysis, persona_id, persona_name, persisted }`.

### Task 7: Frontend — Store + UI

**Files:**
- Modify: `frontend/src/store/appStore.ts`
- Modify: `frontend/src/components/EditorShell.tsx`
- Modify: `frontend/src/app/globals.css`

- [x] Store: persona modal state via `openPersonaModal({ mode, personaId? })`.
- [x] `AgentBody` for `audience`:
  - Persona chips driven by `project.personas`; `+` opens modal; pencil opens edit.
  - Audience analysis card with summary, three score chips, expandable risks/liked/rejected/suggestions.
  - Stale badge when `project.stale.audience`.
- [x] Persona modal component (create/edit/delete) with controlled inputs.
- [x] On stream `artifact` for `audience_analysis` (or done `analysisPersisted`), refetch project so card refreshes.

### Task 8: Verification

**Files:**
- Modify: `docs/development_plan_P0.md` (check Phase 4 boxes)

- [x] `uv run -m pytest` clean (78 tests).
- [x] `npm run typecheck` clean.
- [ ] Manual smoke per design spec §9 acceptance list.
