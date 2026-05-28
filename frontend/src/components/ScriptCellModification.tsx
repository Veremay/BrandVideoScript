"use client";

import { useMemo } from "react";

import type { HunkDecision, ModificationSchemeHunk } from "@/lib/types";

import { useRevisionProposals } from "@/components/RevisionProposalsPanel";

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
          className={`editor-cell-hunk-btn editor-cell-hunk-btn--accept ${decision === true ? "active accept" : ""}`}
          onClick={onAccept}
          type="button"
        >
          Accept
        </button>
        <button
          className={`editor-cell-hunk-btn editor-cell-hunk-btn--reject ${decision === false ? "active reject" : ""}`}
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
  const { selectedScheme, hunkDecisions, setHunkDecision, acceptAndApplyHunk } = useRevisionProposals();

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
    acceptAndApplyHunk,
    hasActiveScheme: Boolean(selectedScheme?.hunks.length)
  };
}
