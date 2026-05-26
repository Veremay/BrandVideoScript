import type { HunkDecision, ModificationScheme, ModificationSchemeHunk, Script, ScriptColumn } from "@/lib/types";

export type SchemePreviewCell = {
  hunkId: string;
  rowId: string;
  rowOrder: number;
  columnId: string;
  columnLabel: string;
  removed: string;
  added: string;
  decision: HunkDecision;
};

function sortedRows(script: Script) {
  return [...script.rows].sort((a, b) => a.order - b.order);
}

function columnLabel(script: Script, columnId: string): string {
  return script.columns.find((column) => column.column_id === columnId)?.label ?? columnId;
}

function cellValue(script: Script, rowId: string, columnId: string): string {
  const row = script.rows.find((item) => item.row_id === rowId);
  if (!row) return "";
  return row.cells.find((cell) => cell.column_id === columnId)?.value ?? "";
}

export function listSchemePreviewCells(
  script: Script,
  scheme: ModificationScheme,
  hunkDecisions: Record<string, HunkDecision>
): SchemePreviewCell[] {
  const rowOrderById = new Map(sortedRows(script).map((row, index) => [row.row_id, index + 1]));

  return scheme.hunks.map((hunk) => ({
    hunkId: hunk.hunk_id,
    rowId: hunk.row_id,
    rowOrder: rowOrderById.get(hunk.row_id) ?? 0,
    columnId: hunk.column_id,
    columnLabel: hunk.context || columnLabel(script, hunk.column_id),
    removed: hunk.removed,
    added: hunk.added,
    decision: hunkDecisions[hunk.hunk_id] ?? null
  }));
}

export function applyHunksToScriptCopy(script: Script, hunks: ModificationSchemeHunk[], hunkIds: string[]): Script {
  const applySet = new Set(hunkIds);
  const next: Script = JSON.parse(JSON.stringify(script)) as Script;

  for (const hunk of hunks) {
    if (!applySet.has(hunk.hunk_id)) continue;
    const current = cellValue(next, hunk.row_id, hunk.column_id);
    if (current !== hunk.removed) continue;
    for (const row of next.rows) {
      if (row.row_id !== hunk.row_id) continue;
      for (const cell of row.cells) {
        if (cell.column_id === hunk.column_id) {
          cell.value = hunk.added;
        }
      }
    }
  }
  return next;
}

export type PreviewTableRow = {
  rowId: string;
  rowOrder: number;
  cells: Array<{
    column: ScriptColumn;
    value: string;
    change?: "accepted" | "rejected" | "pending" | "proposed";
    hunkId?: string;
  }>;
};

/** Rows affected by scheme hunks, with preview values for accepted / all-proposed modes. */
export function buildPreviewTable(
  script: Script,
  scheme: ModificationScheme,
  hunkDecisions: Record<string, HunkDecision>,
  mode: "all_proposed" | "accepted_only"
): PreviewTableRow[] {
  const affectedRowIds = new Set(scheme.hunks.map((hunk) => hunk.row_id));
  const hunkByCell = new Map(scheme.hunks.map((hunk) => [`${hunk.row_id}:${hunk.column_id}`, hunk]));

  const acceptedIds = scheme.hunks
    .filter((hunk) => {
      const decision = hunkDecisions[hunk.hunk_id] ?? null;
      if (mode === "accepted_only") return decision === true;
      return decision !== false;
    })
    .map((hunk) => hunk.hunk_id);

  const previewScript = applyHunksToScriptCopy(script, scheme.hunks, acceptedIds);

  return sortedRows(script)
    .filter((row) => affectedRowIds.has(row.row_id))
    .map((row, index) => {
      const previewRow = previewScript.rows.find((item) => item.row_id === row.row_id);
      const editableColumns = [...script.columns]
        .filter((column) => column.key !== "feedback")
        .sort((a, b) => a.order - b.order);

      return {
        rowId: row.row_id,
        rowOrder: index + 1,
        cells: editableColumns.map((column) => {
          const hunk = hunkByCell.get(`${row.row_id}:${column.column_id}`);
          const original = cellValue(script, row.row_id, column.column_id);
          const decision = hunk ? (hunkDecisions[hunk.hunk_id] ?? null) : null;
          let displayValue = original;
          if (hunk) {
            if (decision === false) {
              displayValue = original;
            } else if (mode === "accepted_only" && decision !== true) {
              displayValue = original;
            } else {
              displayValue =
                previewRow?.cells.find((cell) => cell.column_id === column.column_id)?.value ?? hunk.added;
            }
          }

          let change: PreviewTableRow["cells"][0]["change"];
          if (hunk) {
            if (decision === true) change = "accepted";
            else if (decision === false) change = "rejected";
            else change = "pending";
          }

          return {
            column,
            value: displayValue,
            change: hunk ? change : undefined,
            hunkId: hunk?.hunk_id
          };
        })
      };
    });
}

export function schemeDecisionSummary(
  scheme: ModificationScheme,
  hunkDecisions: Record<string, HunkDecision>
): { accepted: number; rejected: number; pending: number; total: number } {
  let accepted = 0;
  let rejected = 0;
  let pending = 0;
  for (const hunk of scheme.hunks) {
    const decision = hunkDecisions[hunk.hunk_id] ?? null;
    if (decision === true) accepted += 1;
    else if (decision === false) rejected += 1;
    else pending += 1;
  }
  return { accepted, rejected, pending, total: scheme.hunks.length };
}
