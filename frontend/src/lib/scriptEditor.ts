import type { Script, ScriptColumn, ScriptRow } from "@/lib/types";

/** Brand partners fill this on the share page; read-only in the creator workspace (Phase 6 sync). */
export const BRAND_FEEDBACK_COLUMN_KEY = "feedback";

export function isBrandFeedbackColumn(column: Pick<ScriptColumn, "key">) {
  return column.key === BRAND_FEEDBACK_COLUMN_KEY;
}

export function isMultilineColumn(column: Pick<ScriptColumn, "key" | "multiline">) {
  return column.multiline || column.key === "format";
}

export type DurationIssue = {
  rowIds: string[];
  message: string;
  range?: string;
};

export type TimelineSegment = {
  rowId: string;
  start: number;
  end: number;
  left: number;
  width: number;
  hasOverlap: boolean;
};

export type TimelineOverlap = {
  start: number;
  end: number;
  left: number;
  width: number;
};

function clientId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function sortedColumns(script: Script) {
  return [...script.columns].sort((a, b) => a.order - b.order);
}

function sortedRows(script: Script) {
  return [...script.rows].sort((a, b) => a.order - b.order);
}

function reorder<T extends { order: number }>(items: T[]) {
  return items.map((item, order) => ({ ...item, order }));
}

function emptyCells(columns: ScriptColumn[]) {
  return columns.map((column) => ({ column_id: column.column_id, value: "" }));
}

function alignRowCells(row: ScriptRow, columns: ScriptColumn[]) {
  const cellsById = new Map(row.cells.map((cell) => [cell.column_id, cell]));
  return {
    ...row,
    cells: columns.map((column) => cellsById.get(column.column_id) ?? { column_id: column.column_id, value: "" })
  };
}

export function updateCellValue(script: Script, rowId: string, columnId: string, value: string): Script {
  const column = script.columns.find((item) => item.column_id === columnId);
  if (column && isBrandFeedbackColumn(column)) {
    return script;
  }

  return {
    ...script,
    rows: script.rows.map((row) =>
      row.row_id === rowId
        ? {
            ...row,
            cells: row.cells.map((cell) => (cell.column_id === columnId ? { ...cell, value } : cell))
          }
        : row
    )
  };
}

export function insertRow(script: Script, afterRowId?: string): Script {
  const columns = sortedColumns(script);
  const rows = sortedRows(script);
  const insertAt = afterRowId === undefined ? 0 : afterRowId ? rows.findIndex((row) => row.row_id === afterRowId) + 1 : rows.length;
  const safeInsertAt = insertAt >= 0 ? insertAt : rows.length;
  const nextRow: ScriptRow = {
    row_id: clientId("row"),
    order: safeInsertAt,
    cells: emptyCells(columns)
  };

  return {
    ...script,
    rows: reorder([...rows.slice(0, safeInsertAt), nextRow, ...rows.slice(safeInsertAt)])
  };
}

export function removeRow(script: Script, rowId: string): Script {
  const rows = sortedRows(script);
  if (rows.length <= 1) {
    throw new Error("Keep at least one script row.");
  }
  return {
    ...script,
    rows: reorder(rows.filter((row) => row.row_id !== rowId))
  };
}

export function insertColumn(script: Script, afterColumnId?: string, label = "New Column", multiline = false): Script {
  const columns = sortedColumns(script);
  const insertAt = afterColumnId === undefined ? 0 : afterColumnId ? columns.findIndex((column) => column.column_id === afterColumnId) + 1 : columns.length;
  const safeInsertAt = insertAt >= 0 ? insertAt : columns.length;
  const nextColumn: ScriptColumn = {
    column_id: clientId("col"),
    key: `custom_${clientId("field")}`,
    label,
    type: multiline ? "textarea" : "text",
    multiline,
    order: safeInsertAt
  };
  const nextColumns = reorder([...columns.slice(0, safeInsertAt), nextColumn, ...columns.slice(safeInsertAt)]);

  return {
    ...script,
    columns: nextColumns,
    rows: sortedRows(script).map((row) => alignRowCells(row, nextColumns))
  };
}

export function removeColumn(script: Script, columnId: string): Script {
  const columns = sortedColumns(script);
  if (columns.length <= 1) {
    throw new Error("Keep at least one business column.");
  }
  const target = columns.find((column) => column.column_id === columnId);
  if (target?.key === "duration") {
    throw new Error("The Duration column cannot be deleted.");
  }
  if (target && isBrandFeedbackColumn(target)) {
    throw new Error("The Brand Feedback column cannot be deleted.");
  }
  const nextColumns = reorder(columns.filter((column) => column.column_id !== columnId));
  return {
    ...script,
    columns: nextColumns,
    rows: sortedRows(script).map((row) => ({
      ...row,
      cells: row.cells.filter((cell) => cell.column_id !== columnId)
    }))
  };
}

export function renameColumn(script: Script, columnId: string, label: string): Script {
  return {
    ...script,
    columns: script.columns.map((column) => (column.column_id === columnId ? { ...column, label } : column))
  };
}

/** Parse a seconds-only duration. Legacy start-end ranges are intentionally unsupported. */
export function parseDurationSeconds(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  const seconds = Number(trimmed);
  if (Number.isFinite(seconds) && seconds > 0) return seconds;
  return null;
}

/** Old start-end values are cleared instead of being reinterpreted as durations. */
export function durationInputValue(value: string): string {
  return /^\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*$/.test(value) ? "" : value;
}

function formatSeconds(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, "");
}

export function analyzeDurations(script: Script): {
  issues: DurationIssue[];
  overlaps: TimelineOverlap[];
  timeline: TimelineSegment[];
} {
  const durationColumn = script.columns.find((column) => column.type === "duration");
  if (!durationColumn) {
    return { issues: [], overlaps: [], timeline: [] };
  }

  let cursor = 0;
  const ranges = sortedRows(script)
    .map((row) => {
      const value = row.cells.find((cell) => cell.column_id === durationColumn.column_id)?.value ?? "";
      const inputValue = durationInputValue(value);
      const seconds = parseDurationSeconds(inputValue);
      if (seconds !== null) {
        const start = cursor;
        const end = start + seconds;
        cursor = end;
        return { rowId: row.row_id, start, end };
      }
      return inputValue ? { rowId: row.row_id, invalid: true } : null;
    })
    .filter(Boolean) as Array<{ rowId: string; start?: number; end?: number; invalid?: boolean }>;

  const issues: DurationIssue[] = ranges
    .filter((range) => range.invalid)
    .map((range) => ({ rowIds: [range.rowId], message: "Enter a positive number of seconds, e.g. 5 or 2.5." }));

  const validRanges = ranges.filter((range) => range.start !== undefined && range.end !== undefined) as Array<{
    rowId: string;
    start: number;
    end: number;
  }>;

  const maxEnd = Math.max(1, ...validRanges.map((range) => range.end));
  return {
    issues,
    overlaps: [],
    timeline: validRanges.map((range) => ({
      rowId: range.rowId,
      start: range.start,
      end: range.end,
      left: (range.start / maxEnd) * 100,
      width: ((range.end - range.start) / maxEnd) * 100,
      hasOverlap: false
    }))
  };
}
