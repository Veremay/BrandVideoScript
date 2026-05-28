"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

import { applyModificationSchemeHunks } from "@/lib/api";
import {
  buildPreviewTable,
  listSchemePreviewCells,
  schemeDecisionSummary
} from "@/lib/schemePreview";
import { isStaleStatus } from "@/lib/stale";
import type { HunkDecision, ModificationScheme, ModificationSchemeDirection, Script } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

const DIRECTION_LABELS: Record<ModificationSchemeDirection, string> = {
  conservative: "Conservative · Brand-first",
  balanced: "Balanced",
  creator_led: "Creator-led",
  audience_friendly: "Audience-friendly",
  custom: "Custom"
};

type PreviewMode = "all_proposed" | "accepted_only";

type RevisionProposalsContextValue = {
  projectId: string;
  userId: string;
  schemes: ModificationScheme[];
  schemesStale: boolean;
  selectedSchemeId: string | null;
  setSelectedSchemeId: (id: string) => void;
  selectedScheme: ModificationScheme | null;
  activeScript: Script | null;
  previewOpen: boolean;
  setPreviewOpen: (open: boolean) => void;
  hunkDecisions: Record<string, HunkDecision>;
  setHunkDecision: (hunkId: string, decision: HunkDecision) => void;
  previewMode: PreviewMode;
  setPreviewMode: (mode: PreviewMode) => void;
  summary: ReturnType<typeof schemeDecisionSummary> | null;
  previewTable: ReturnType<typeof buildPreviewTable>;
  applying: boolean;
  error: string | null;
  statusMessage: string | null;
  acceptAllAndApply: () => Promise<void>;
  applyAcceptedOnly: () => Promise<void>;
  rejectAllHunks: () => void;
  acceptAndApplyHunk: (hunkId: string) => Promise<void>;
  selectScheme: (schemeId: string) => void;
};

const RevisionProposalsContext = createContext<RevisionProposalsContextValue | null>(null);

export function useRevisionProposals() {
  const ctx = useContext(RevisionProposalsContext);
  if (!ctx) {
    throw new Error("RevisionProposals components must be used within RevisionProposalsProvider");
  }
  return ctx;
}

type RevisionProposalsProviderProps = {
  projectId: string;
  userId: string;
  children: ReactNode;
};

export function RevisionProposalsProvider({ projectId, userId, children }: RevisionProposalsProviderProps) {
  const project = useAppStore((state) => state.project);
  const script = useAppStore((state) => state.script);
  const setProject = useAppStore((state) => state.setProject);
  const setScript = useAppStore((state) => state.setScript);

  const schemes = useMemo(() => {
    const all = project?.modification_schemes ?? [];
    return all.length ? [all[all.length - 1]] : [];
  }, [project?.modification_schemes]);
  const schemesStale = isStaleStatus(project?.stale?.modification_schemes);

  const [selectedSchemeId, setSelectedSchemeId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [hunkDecisions, setHunkDecisions] = useState<Record<string, HunkDecision>>({});
  const [previewMode, setPreviewMode] = useState<PreviewMode>("all_proposed");
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const selectedScheme = useMemo(
    () => schemes.find((scheme) => scheme.scheme_id === selectedSchemeId) ?? null,
    [schemes, selectedSchemeId]
  );

  const activeScript = script ?? project?.current_script ?? null;

  const summary = useMemo(
    () => (selectedScheme ? schemeDecisionSummary(selectedScheme, hunkDecisions) : null),
    [selectedScheme, hunkDecisions]
  );

  const previewTable = useMemo(() => {
    if (!activeScript || !selectedScheme) return [];
    return buildPreviewTable(activeScript, selectedScheme, hunkDecisions, previewMode);
  }, [activeScript, selectedScheme, hunkDecisions, previewMode]);

  const editorSchemeFocusId = useAppStore((state) => state.editorSchemeFocusId);
  const setEditorSchemeFocusId = useAppStore((state) => state.setEditorSchemeFocusId);

  useEffect(() => {
    if (!selectedSchemeId && schemes.length) {
      setSelectedSchemeId(schemes[schemes.length - 1].scheme_id);
    }
  }, [schemes, selectedSchemeId]);

  useEffect(() => {
    if (!editorSchemeFocusId || !schemes.some((scheme) => scheme.scheme_id === editorSchemeFocusId)) {
      return;
    }
    setSelectedSchemeId(editorSchemeFocusId);
    setPreviewOpen(true);
    setEditorSchemeFocusId(null);
  }, [editorSchemeFocusId, schemes, setEditorSchemeFocusId]);

  useEffect(() => {
    if (!selectedScheme) {
      setHunkDecisions({});
      setPreviewOpen(false);
      return;
    }
    const initial: Record<string, HunkDecision> = {};
    for (const hunk of selectedScheme.hunks) {
      initial[hunk.hunk_id] = null;
    }
    setHunkDecisions(initial);
    setPreviewMode("all_proposed");
  }, [selectedScheme?.scheme_id]);

  const applyHunks = useCallback(
    async (acceptedIds: string[], rejectedIds: string[]) => {
      if (!selectedScheme || !acceptedIds.length) return;
      setApplying(true);
      setError(null);
      setStatusMessage(null);
      try {
        const updated = await applyModificationSchemeHunks(
          projectId,
          userId,
          selectedScheme.scheme_id,
          acceptedIds,
          rejectedIds
        );
        setProject(updated);
        setScript(updated.current_script);
        const total = selectedScheme.hunks.length;
        setStatusMessage(
          acceptedIds.length >= total
            ? "All changes applied to the script."
            : `Applied ${acceptedIds.length} of ${total} changes. Roll back from version history if needed.`
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to apply changes");
      } finally {
        setApplying(false);
      }
    },
    [projectId, selectedScheme, setProject, setScript, userId]
  );

  const acceptAllAndApply = useCallback(async () => {
    if (!selectedScheme?.hunks.length) return;
    const acceptedIds = selectedScheme.hunks.map((hunk) => hunk.hunk_id);
    const next: Record<string, HunkDecision> = {};
    for (const id of acceptedIds) next[id] = true;
    setHunkDecisions(next);
    setPreviewMode("accepted_only");
    await applyHunks(acceptedIds, []);
  }, [applyHunks, selectedScheme]);

  const applyAcceptedOnly = useCallback(async () => {
    const acceptedIds = Object.entries(hunkDecisions)
      .filter(([, value]) => value === true)
      .map(([id]) => id);
    const rejectedIds = Object.entries(hunkDecisions)
      .filter(([, value]) => value === false)
      .map(([id]) => id);
    if (!acceptedIds.length) {
      setError("Accept individual changes in the preview below, or use Accept All.");
      return;
    }
    await applyHunks(acceptedIds, rejectedIds);
  }, [applyHunks, hunkDecisions]);

  const rejectAllHunks = useCallback(() => {
    if (!selectedScheme) return;
    const next: Record<string, HunkDecision> = {};
    for (const hunk of selectedScheme.hunks) {
      next[hunk.hunk_id] = false;
    }
    setHunkDecisions(next);
    setPreviewMode("accepted_only");
    setStatusMessage(null);
    setError(null);
  }, [selectedScheme]);

  const setHunkDecision = useCallback((hunkId: string, decision: HunkDecision) => {
    setHunkDecisions((prev) => ({ ...prev, [hunkId]: decision }));
  }, []);

  const acceptAndApplyHunk = useCallback(
    async (hunkId: string) => {
      if (schemesStale) {
        setError("Script changed — regenerate the plan before applying.");
        return;
      }
      setHunkDecisions((prev) => ({ ...prev, [hunkId]: true }));
      await applyHunks([hunkId], []);
    },
    [applyHunks, schemesStale]
  );

  const selectScheme = useCallback(
    (schemeId: string) => {
      if (schemeId === selectedSchemeId && previewOpen) {
        setPreviewOpen(false);
        return;
      }
      setSelectedSchemeId(schemeId);
      setPreviewOpen(true);
    },
    [previewOpen, selectedSchemeId]
  );

  const value: RevisionProposalsContextValue = {
    projectId,
    userId,
    schemes,
    schemesStale,
    selectedSchemeId,
    setSelectedSchemeId,
    selectedScheme,
    activeScript,
    previewOpen,
    setPreviewOpen,
    hunkDecisions,
    setHunkDecision,
    previewMode,
    setPreviewMode,
    summary,
    previewTable,
    applying,
    error,
    statusMessage,
    acceptAllAndApply,
    applyAcceptedOnly,
    rejectAllHunks,
    acceptAndApplyHunk,
    selectScheme
  };

  return <RevisionProposalsContext.Provider value={value}>{children}</RevisionProposalsContext.Provider>;
}

/** Scrollable plan cards + optional preview (mock-style list area). */
export function RevisionProposalsList() {
  const {
    schemes,
    schemesStale,
    selectedSchemeId,
    selectedScheme,
    activeScript,
    previewOpen,
    previewMode,
    previewTable,
    summary,
    hunkDecisions,
    setHunkDecision,
    setPreviewMode,
    error,
    statusMessage,
    selectScheme
  } = useRevisionProposals();

  return (
    <div className="glacier-plans-list">
      {schemesStale ? (
        <p className="glacier-plans-stale-banner">
          Script changed. Ask Coordinator to regenerate revision proposals before applying.
        </p>
      ) : null}
      {error ? <p className="glacier-stream-error">{error}</p> : null}
      {statusMessage ? <p className="glacier-plans-status">{statusMessage}</p> : null}

      {!schemes.length ? (
        <p className="glacier-plans-placeholder">
          No revision proposals yet. In Chat, ask Coordinator to generate a modification scheme for adopted positions.
        </p>
      ) : null}

      {schemes.map((scheme) => (
        <SchemeCard
          key={scheme.scheme_id}
          active={scheme.scheme_id === selectedSchemeId}
          previewing={scheme.scheme_id === selectedSchemeId && previewOpen}
          scheme={scheme}
          onSelect={() => selectScheme(scheme.scheme_id)}
        />
      ))}

      {previewOpen && selectedScheme && activeScript ? (
        <>
          <ScriptSchemePreview
            previewMode={previewMode}
            previewTable={previewTable}
            summary={summary}
            onPreviewModeChange={setPreviewMode}
          />
          <SchemeDetail
            scheme={selectedScheme}
            script={activeScript}
            hunkDecisions={hunkDecisions}
            onHunkDecision={setHunkDecision}
          />
        </>
      ) : null}
    </div>
  );
}

/** Fixed footer actions (mock-style), rendered outside glacier-body scroll. */
export function RevisionProposalsActions() {
  const { schemes, schemesStale, selectedScheme, applying, acceptAllAndApply, applyAcceptedOnly, rejectAllHunks } =
    useRevisionProposals();

  if (!schemes.length) return null;

  const hasHunks = Boolean(selectedScheme?.hunks.length);
  const disabled = applying || schemesStale || !selectedScheme;

  return (
    <div className="glacier-plans-actions">
      <div className="glacier-plans-actions-row">
        <button
          className="glacier-btn glacier-btn--primary"
          disabled={disabled || !hasHunks}
          onClick={() => void acceptAllAndApply()}
          type="button"
        >
          {applying ? "Applying…" : "Accept All"}
        </button>
        <button
          className="glacier-btn glacier-btn--outline"
          disabled={disabled || !hasHunks}
          onClick={() => void applyAcceptedOnly()}
          type="button"
        >
          Accept Map Only
        </button>
      </div>
      <button
        className="glacier-reject-all"
        disabled={disabled || !hasHunks}
        onClick={rejectAllHunks}
        type="button"
      >
        Reject All
      </button>
    </div>
  );
}

/** @deprecated Use Provider + List + Actions in CoordinatorChat */
export function RevisionProposalsPanel({ projectId, userId }: { projectId: string; userId: string }) {
  return (
    <RevisionProposalsProvider projectId={projectId} userId={userId}>
      <RevisionProposalsList />
      <RevisionProposalsActions />
    </RevisionProposalsProvider>
  );
}

function SchemeCard({
  scheme,
  active,
  previewing,
  onSelect
}: {
  scheme: ModificationScheme;
  active: boolean;
  previewing: boolean;
  onSelect: () => void;
}) {
  return (
    <article className={`glacier-plan-card ${active ? "glacier-plan-card--active" : ""}`}>
      <div className="glacier-plan-head">
        <h3 className="glacier-plan-title">{scheme.title}</h3>
        {active ? <span className="glacier-plan-badge">ACTIVE</span> : null}
      </div>
      <p className="glacier-plan-desc">{scheme.changes_summary || scheme.rationale}</p>
      <p className="glacier-plan-meta">{DIRECTION_LABELS[scheme.direction] ?? scheme.direction}</p>
      <button
        className={`glacier-plan-btn ${active && previewing ? "glacier-plan-btn--active" : ""}`}
        onClick={onSelect}
        type="button"
      >
        {active && previewing ? "Currently Previewing" : "Preview Plan"}
      </button>
    </article>
  );
}

function ScriptSchemePreview({
  previewTable,
  previewMode,
  summary,
  onPreviewModeChange
}: {
  previewTable: ReturnType<typeof buildPreviewTable>;
  previewMode: PreviewMode;
  summary: ReturnType<typeof schemeDecisionSummary> | null;
  onPreviewModeChange: (mode: PreviewMode) => void;
}) {
  if (!previewTable.length) return null;

  return (
    <section className="glacier-script-preview">
      <div className="glacier-script-preview-head">
        <h4 className="glacier-scheme-detail-title">Script preview</h4>
        <div className="glacier-preview-mode" role="tablist" aria-label="Preview mode">
          <button
            className={previewMode === "all_proposed" ? "active" : ""}
            onClick={() => onPreviewModeChange("all_proposed")}
            type="button"
          >
            Full proposal
          </button>
          <button
            className={previewMode === "accepted_only" ? "active" : ""}
            onClick={() => onPreviewModeChange("accepted_only")}
            type="button"
            disabled={!summary?.accepted}
          >
            Accepted only
          </button>
        </div>
      </div>
      <p className="glacier-script-preview-note">
        Affected script rows only. Green highlights will be written; strikethrough is the current text.
      </p>
      <div className="glacier-script-preview-table-wrap">
        <table className="glacier-script-preview-table">
          <thead>
            <tr>
              <th>#</th>
              {previewTable[0]?.cells.map((cell) => (
                <th key={cell.column.column_id}>{cell.column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {previewTable.map((row) => (
              <tr key={row.rowId}>
                <td className="glacier-preview-row-num">{row.rowOrder}</td>
                {row.cells.map((cell) => (
                  <td
                    className={[
                      "glacier-preview-cell",
                      cell.change === "accepted" ? "is-accepted" : "",
                      cell.change === "rejected" ? "is-rejected" : "",
                      cell.change === "pending" ? "is-pending" : "",
                      cell.change === "proposed" ? "is-proposed" : ""
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    key={cell.column.column_id}
                  >
                    {cell.change && cell.change !== "rejected" ? (
                      <span className="glacier-preview-value">{cell.value || "(empty)"}</span>
                    ) : (
                      <span className="glacier-preview-value glacier-preview-value--unchanged">
                        {cell.value || "(empty)"}
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function EditorModificationPlan() {
  const {
    schemes,
    schemesStale,
    selectedSchemeId,
    selectedScheme,
    activeScript,
    hunkDecisions,
    setHunkDecision,
    summary,
    applying,
    error,
    statusMessage,
    acceptAllAndApply,
    applyAcceptedOnly,
    rejectAllHunks,
    setSelectedSchemeId,
    setPreviewOpen
  } = useRevisionProposals();

  if (!schemes.length) return null;

  return (
    <aside className="editor-modification-panel" aria-label="Modification plan">
      <header className="editor-modification-head">
        <h2 className="editor-modification-title">Modification plan</h2>
        {schemesStale ? (
          <p className="editor-modification-stale">Script changed — regenerate from Map before applying.</p>
        ) : null}
      </header>
      {error ? <p className="editor-modification-error">{error}</p> : null}
      {statusMessage ? <p className="editor-modification-status">{statusMessage}</p> : null}

      <div className="editor-modification-schemes" role="tablist" aria-label="Scheme options">
        {schemes.map((scheme) => (
          <button
            className={`editor-modification-scheme-tab ${scheme.scheme_id === selectedSchemeId ? "active" : ""}`}
            key={scheme.scheme_id}
            onClick={() => {
              setSelectedSchemeId(scheme.scheme_id);
              setPreviewOpen(true);
            }}
            type="button"
            role="tab"
            aria-selected={scheme.scheme_id === selectedSchemeId}
          >
            {DIRECTION_LABELS[scheme.direction] ?? scheme.direction}
          </button>
        ))}
      </div>

      {selectedScheme && activeScript ? (
        <SchemeDetail
          scheme={selectedScheme}
          script={activeScript}
          hunkDecisions={hunkDecisions}
          onHunkDecision={setHunkDecision}
        />
      ) : null}

      {summary && selectedScheme?.hunks.length ? (
        <p className="editor-modification-summary">
          {summary.accepted} accepted · {summary.rejected} rejected · {summary.pending} pending
        </p>
      ) : null}

      {selectedScheme?.hunks.length ? (
        <div className="editor-modification-actions">
          <button
            className="editor-modification-btn editor-modification-btn--primary"
            disabled={applying || schemesStale}
            onClick={() => void acceptAllAndApply()}
            type="button"
          >
            {applying ? "Applying…" : "Accept all & apply"}
          </button>
          <button
            className="editor-modification-btn"
            disabled={applying || schemesStale}
            onClick={() => void applyAcceptedOnly()}
            type="button"
          >
            Apply accepted only
          </button>
          <button
            className="editor-modification-btn editor-modification-btn--ghost"
            disabled={applying || schemesStale}
            onClick={rejectAllHunks}
            type="button"
          >
            Reject all
          </button>
        </div>
      ) : null}
    </aside>
  );
}

function SchemeDetail({
  scheme,
  script,
  hunkDecisions,
  onHunkDecision
}: {
  scheme: ModificationScheme;
  script: Script;
  hunkDecisions: Record<string, HunkDecision>;
  onHunkDecision: (hunkId: string, decision: HunkDecision) => void;
}) {
  const cells = listSchemePreviewCells(script, scheme, hunkDecisions);

  return (
    <section className="glacier-scheme-detail">
      <h4 className="glacier-scheme-detail-title">Change details</h4>
      {scheme.rationale ? <p className="glacier-scheme-detail-text">{scheme.rationale}</p> : null}
      {scheme.sacrifice ? (
        <p className="glacier-scheme-detail-meta">
          <strong>Trade-off:</strong> {scheme.sacrifice}
        </p>
      ) : null}
      {scheme.response_script ? (
        <p className="glacier-scheme-detail-meta">
          <strong>Response script:</strong> {scheme.response_script}
        </p>
      ) : null}

      {cells.length ? (
        <>
          <h5 className="glacier-hunk-list-title">Review each change</h5>
          <ul className="glacier-hunk-list">
            {cells.map((cell) => (
              <li
                className={[
                  "glacier-hunk-item",
                  cell.decision === true ? "is-accepted" : "",
                  cell.decision === false ? "is-rejected" : ""
                ]
                  .filter(Boolean)
                  .join(" ")}
                key={cell.hunkId}
              >
                <p className="glacier-hunk-context">
                  Row {cell.rowOrder} · {cell.columnLabel}
                </p>
                <div className="glacier-hunk-diff">
                  <del className="glacier-hunk-removed">{cell.removed || "(empty)"}</del>
                  <span className="glacier-hunk-arrow" aria-hidden="true">
                    →
                  </span>
                  <ins className="glacier-hunk-added">{cell.added}</ins>
                </div>
                <div className="glacier-hunk-actions" role="group" aria-label="Hunk decision">
                  <button
                    className={`glacier-hunk-btn ${cell.decision === true ? "active accept" : ""}`}
                    onClick={() => onHunkDecision(cell.hunkId, true)}
                    type="button"
                  >
                    Accept
                  </button>
                  <button
                    className={`glacier-hunk-btn ${cell.decision === false ? "active reject" : ""}`}
                    onClick={() => onHunkDecision(cell.hunkId, false)}
                    type="button"
                  >
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="glacier-plans-placeholder">Strategy-only proposal with no script cell edits.</p>
      )}
    </section>
  );
}
