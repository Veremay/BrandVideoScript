"use client";

import { useMemo } from "react";

import type { HunkDecision, ModificationSchemeHunk } from "@/lib/types";

import { useRevisionProposals } from "@/components/RevisionProposalsPanel";

const DIRECTION_SHORT: Record<string, string> = {
  conservative: "Brand-first",
  balanced: "Balanced",
  creator_led: "Creator-led",
  audience_friendly: "Audience-friendly",
  custom: "Custom"
};

export function ScriptModificationBar() {
  const {
    schemes,
    schemesStale,
    selectedSchemeId,
    selectedScheme,
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

  const disabled = applying || schemesStale || !selectedScheme;
  const hasHunks = Boolean(selectedScheme?.hunks.length);

  return (
    <div className="script-modification-bar" role="region" aria-label="Modification plan">
      <div className="script-modification-bar-head">
        <span className="script-modification-bar-label">Modification plan</span>
        {schemesStale ? (
          <span className="script-modification-bar-stale">Script changed — regenerate from Map</span>
        ) : null}
        {summary && hasHunks ? (
          <span className="script-modification-bar-summary">
            {summary.accepted} accepted · {summary.rejected} rejected · {summary.pending} pending
          </span>
        ) : null}
      </div>
      {error ? <p className="script-modification-bar-message script-modification-bar-message--error">{error}</p> : null}
      {statusMessage ? (
        <p className="script-modification-bar-message script-modification-bar-message--ok">{statusMessage}</p>
      ) : null}
      <div className="script-modification-bar-row">
        <div className="script-modification-schemes" role="tablist" aria-label="Scheme direction">
          {schemes.map((scheme) => (
            <button
              className={`script-modification-scheme-tab ${scheme.scheme_id === selectedSchemeId ? "active" : ""}`}
              key={scheme.scheme_id}
              onClick={() => {
                setSelectedSchemeId(scheme.scheme_id);
                setPreviewOpen(true);
              }}
              type="button"
              role="tab"
              aria-selected={scheme.scheme_id === selectedSchemeId}
            >
              {DIRECTION_SHORT[scheme.direction] ?? scheme.direction}
            </button>
          ))}
        </div>
        {hasHunks ? (
          <div className="script-modification-bar-actions">
            <button
              className="script-modification-action script-modification-action--primary"
              disabled={disabled}
              onClick={() => void acceptAllAndApply()}
              type="button"
            >
              {applying ? "Applying…" : "Accept all & apply"}
            </button>
            <button
              className="script-modification-action"
              disabled={disabled}
              onClick={() => void applyAcceptedOnly()}
              type="button"
            >
              Apply accepted
            </button>
            <button
              className="script-modification-action script-modification-action--ghost"
              disabled={disabled}
              onClick={rejectAllHunks}
              type="button"
            >
              Reject all
            </button>
          </div>
        ) : null}
      </div>
      {selectedScheme?.changes_summary ? (
        <p className="script-modification-bar-desc">{selectedScheme.changes_summary}</p>
      ) : null}
    </div>
  );
}

export function CellHunkDiff({
  hunk,
  decision,
  onAccept,
  onReject
}: {
  hunk: ModificationSchemeHunk;
  decision: HunkDecision;
  onAccept: () => void;
  onReject: () => void;
}) {
  const stateClass =
    decision === true ? "is-accepted" : decision === false ? "is-rejected" : "is-pending";

  return (
    <div className={`editor-cell-hunk ${stateClass}`}>
      <div className="editor-cell-hunk-diff">
        <del className="editor-cell-hunk-removed">{hunk.removed || "(empty)"}</del>
        <span className="editor-cell-hunk-arrow" aria-hidden="true">
          →
        </span>
        <ins className="editor-cell-hunk-added">{hunk.added}</ins>
      </div>
      <div className="editor-cell-hunk-actions" role="group" aria-label="Accept or reject change">
        <button
          className={`editor-cell-hunk-btn ${decision === true ? "active accept" : ""}`}
          onClick={onAccept}
          type="button"
        >
          Accept
        </button>
        <button
          className={`editor-cell-hunk-btn ${decision === false ? "active reject" : ""}`}
          onClick={onReject}
          type="button"
        >
          Reject
        </button>
      </div>
    </div>
  );
}

export function useCellHunkMap() {
  const { selectedScheme, hunkDecisions, setHunkDecision } = useRevisionProposals();

  const hunkByCell = useMemo(() => {
    const map = new Map<string, ModificationSchemeHunk>();
    if (selectedScheme) {
      for (const hunk of selectedScheme.hunks) {
        map.set(`${hunk.row_id}:${hunk.column_id}`, hunk);
      }
    }
    return map;
  }, [selectedScheme]);

  return {
    hunkByCell,
    hunkDecisions,
    setHunkDecision,
    hasActiveScheme: Boolean(selectedScheme?.hunks.length)
  };
}
