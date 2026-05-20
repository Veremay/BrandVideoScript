# Phase 5 Expert Loop Implementation Plan

> **Design spec (authoritative):** `docs/superpowers/specs/2026-05-19-phase-5-expert-loop-design.md`

**Goal:** Multi-proposal Expert Agent with cell-level hunks; diff overlay with per-hunk accept/reject; snapshot-backed apply that respects `hunk.old == current cell`.

**Architecture:** Add a third structured artifact channel (`<expert_suggestions>`) alongside the brand / audience ones. Persist suggestions on `project.expert_suggestions`; persist snapshots on a new `script_snapshots` collection. Reuse SSE plumbing.

**Tech Stack:** FastAPI, Motor/MongoDB, Pydantic, Next.js, React, Zustand, TypeScript, SiliconFlow (Qwen3-32B for suggestion generation).

---

### Task 1: Backend — ExpertSuggestion + Hunk data layer

**Files:**
- Modify: `backend/app/repositories/projects.py`
- Modify: `backend/app/models/schemas.py`
- Test: `backend/tests/test_expert_ops.py`

- [ ] `EXPERT_DIRECTIONS`, `EXPERT_SUGGESTION_STATUS` constants.
- [ ] `build_expert_hunk(...)` and `build_expert_suggestion(...)` helpers with field trimming and validation; auto-generate `hunk_id` / `suggestion_id`.
- [ ] `save_expert_suggestions(db, project_id, user_id, suggestions, *, based_on_brand_insight_ids, based_on_audience_analysis_id)` writes `expert_suggestions = [*existing, ...new]` (sorted by `created_at`) and flips `stale.expert=false`.
- [ ] `update_expert_suggestion_status(db, project_id, user_id, suggestion_id, status)` for dismiss / reopen flow.
- [ ] `apply_expert_suggestion(db, project_id, user_id, suggestion_id, accepted_ids, rejected_ids)` returning `{project, applied_hunk_ids, skipped_hunk_ids, conflict_hunk_ids, before_snapshot_id, after_snapshot_id}`. Uses snapshot repo + dedicated `_apply_script_without_invalidating` writer.
- [ ] Pydantic request models: `ExpertSuggestionApplyRequest`, `ExpertSuggestionStatusRequest`.

### Task 2: Backend — Script snapshot repository

**Files:**
- Create: `backend/app/repositories/script_snapshots.py`
- Modify: `backend/app/models/schemas.py` (`ScriptSnapshotResponse`, `ScriptSnapshotListResponse`, `SnapshotCreateRequest`)
- Test: `backend/tests/test_script_snapshots.py`

- [ ] `build_snapshot(...)` with `reason` enum (`manual_save | before_expert_apply | after_expert_apply | before_restore | import`).
- [ ] `create_snapshot(db, project_id, user_id, *, reason, script, suggestion_id=None, applied_hunk_ids=None)`.
- [ ] `list_snapshots(db, project_id, user_id, *, limit=20)` sorted by `created_at` desc.
- [ ] `get_snapshot(db, project_id, user_id, snapshot_id)`.
- [ ] `restore_snapshot(db, project_id, user_id, snapshot_id)` writes a `before_restore` snapshot then calls `_write_script(snapshot.script)`.

### Task 3: Backend — Expert artifact parser

**Files:**
- Create: `backend/app/services/expert_suggestion_proposals.py`
- Test: `backend/tests/test_expert_suggestion_proposals.py`

- [ ] Match brand / audience parser API: `MARKER_START / MARKER_END / MAX_MARKER_LEN / _OPEN_RE / _CLOSE_RE / find_marker_start / strip_proposal_block / parse_suggestion_items`.
- [ ] Tolerant regex: `<expert_suggestion(?:s|_proposals)?>` (any case).
- [ ] `parse_suggestion_items(text, *, allowed_cells, allowed_columns)`:
  - `allowed_cells: dict[(row_id, column_id), str]` — current cell value to compare against `hunk.old`.
  - `allowed_columns: dict[column_id, {label, type}]` so we can drop hunks against `type=duration` columns.
  - Drop hunks: missing row_id/column_id, column type duration, `old` mismatch with allowed_cells, or empty `new`.
  - Drop suggestion entirely if no valid hunks.
  - Validate `direction` against enum, fallback to `custom`.
  - Truncate fields: title 120, description 600, rationale 800, tradeoff/risk/explanation 600, reason 280.
  - Cap items at 3, hunks at 6 per item.

### Task 4: Backend — Expert prompt + context

**Files:**
- Modify: `backend/app/prompts/expert.md`
- Modify: `backend/app/services/agent_context.py`

- [ ] Rewrite `expert.md`:
  - Sections: 当前合作品牌 / 品牌洞察 / 观众分析详情 / 当前脚本 cells / 用户引用 / 最近对话.
  - Strict rules: 1-3 方案、覆盖 ≥2 方向、`old` 完整匹配、不修改 duration 列、JSON 协议见末尾。
  - Embed full `<expert_suggestions>` schema.
- [ ] Add `format_audience_analysis_detail(project)` exposing persona name, scores, key_risks, liked/rejected parts, suggestions.
- [ ] Add `format_script_cells(script, *, max_chars=240)` producing the row/column-anchored cell listing the parser will use for `allowed_cells`.
- [ ] `build_prompt_variables` exposes `audience_analysis_detail`, `script_cells`.

### Task 5: Backend — agent_stream expert branch

**Files:**
- Modify: `backend/app/services/agent_stream.py`
- Test: extend `backend/tests/test_agent_stream.py`

- [ ] Import `expert_suggestion_proposals as expert_marker`.
- [ ] `_HOLD_TAIL = max(brand, audience, expert)` marker lengths.
- [ ] `_find_marker_start_for("expert", ...)` returns expert marker start.
- [ ] For `agent_type == "expert"`:
  - Build `allowed_cells` from current script (row_id, column_id → value).
  - Build `allowed_columns` map.
  - After stream completion: parse → validate → `save_expert_suggestions(...)` → emit `event: artifact { type: "expert_suggestions", items, persisted_count, trace_run_id }`.
  - Strip block from assistant content before persisting message.
  - `done` payload: `suggestions_persisted_count`.

### Task 6: Backend — apply + snapshot + suggestion routes

**Files:**
- Modify: `backend/app/api/routes/projects.py`

- [ ] `POST /projects/{id}/expert-suggestions/{sid}/apply` (returns `{project, applied_hunk_ids, skipped_hunk_ids, conflict_hunk_ids, before_snapshot_id, after_snapshot_id, applied_hunk_count}`).
- [ ] `PATCH /projects/{id}/expert-suggestions/{sid}` (status only).
- [ ] `GET /projects/{id}/script/snapshots` → returns snapshot list with `script` omitted from list response payload (lighter); detail kept on restore endpoint.
- [ ] `POST /projects/{id}/script/snapshots` → manual_save (uses current `current_script`).
- [ ] `POST /projects/{id}/script/snapshots/{sid}/restore` → restores and returns Project.

### Task 7: Backend — verification

**Files:**
- Run: `uv run -m pytest` (full suite)
- Verify: `backend/tests/test_expert_suggestion_proposals.py`, `test_expert_ops.py`, `test_script_snapshots.py`, expert branch additions in `test_agent_stream.py` all pass.

### Task 8: Frontend — Types + API helpers

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] `ExpertHunk`, `ExpertSuggestion`, `ExpertSuggestionStatus`, `ExpertDirection`, `ScriptSnapshot`, `ScriptSnapshotReason` types.
- [ ] Update `Project.expert_suggestions: ExpertSuggestion[]`.
- [ ] API helpers: `applyExpertSuggestion`, `updateExpertSuggestionStatus`, `listScriptSnapshots`, `saveScriptSnapshot`, `restoreScriptSnapshot`.
- [ ] Extend `AgentStreamArtifact` union with `expert_suggestions` artifact (`items`, `persisted_count`).
- [ ] `AgentStreamDoneInfo` includes `suggestionsPersistedCount`.

### Task 9: Frontend — Store + Expert panel cards

**Files:**
- Modify: `frontend/src/store/appStore.ts`
- Modify: `frontend/src/components/EditorShell.tsx`

- [ ] Store: `expert.activeSuggestionId`, `expert.diffOverlayOpen`, `expert.hunkState` setters (`openDiffOverlay(suggestionId)`, `closeDiffOverlay`, `setHunkState(hunkId, true|false|null)`, `setAllHunks(value)`).
- [ ] Add `ExpertPanel` component rendering proposal cards from `project.expert_suggestions`:
  - Header line: direction chip + title + status badge.
  - Description short text.
  - Buttons: 预览修改 / 展开详情.
  - Expanded body: target_problem / rationale / trade-offs / risk / explanation_to_brand / hunks 概览.
  - Status-aware actions (draft → 预览; applied → 重新预览历史; dismissed → 角标).
- [ ] Replace static mock card in `AgentBody`'s `expert` branch with `ExpertPanel`.
- [ ] On stream artifact `expert_suggestions` (or done `suggestionsPersistedCount>0`), refetch project.

### Task 10: Frontend — Diff Overlay + Topbar entry + Snapshot drawer

**Files:**
- Modify: `frontend/src/components/EditorShell.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] `DiffOverlay` component (modal-style overlay). Reads suggestion + `hunkState`.
- [ ] Per-hunk rendering: row_id / column label header, side-by-side or stacked old/new with red/green tinting, accept/reject buttons.
- [ ] Top action bar: 全部应用 / 全部不应用 / 重置 / 写入编辑器 / 关闭.
- [ ] 写入编辑器 → `applyExpertSuggestion(...)` → toast 提示成功/部分成功/全冲突 → 关闭 overlay 并 setProject.
- [ ] Topbar「预览修改稿」按钮：
  - 若存在 `status="draft"` 的最新 suggestion → 打开 overlay。
  - 否则 toast。
- [ ] `SnapshotDrawer` component (Topbar entry「版本」icon → 弹出右侧抽屉)：
  - 列出最近 20 条快照，显示 reason、`applied_hunk_ids`、时间。
  - 「回退」按钮调用 `restoreScriptSnapshot` → setProject.
- [ ] Styles for diff old/new, hunk popup states, snapshot drawer (sliding panel).

### Task 11: Frontend — verification

**Files:**
- Run: `npm run typecheck`
- Run: `npm run lint` (if available)

- [ ] Typecheck clean.
- [ ] Manual smoke per spec §9 acceptance list (out of scope for this plan — handover note).

### Task 12: Docs

**Files:**
- Modify: `docs/development_plan_P0.md`

- [ ] Tick Phase 5 task rows (5.1–5.7) and §8.5 acceptance list.
