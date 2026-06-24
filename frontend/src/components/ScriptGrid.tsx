"use client";

import { MouseEvent, PointerEvent, useEffect, useMemo, useState } from "react";

import { CellHunkDiff, useCellHunkMap } from "@/components/ScriptCellModification";
import { createGraphNode, toggleCommunicationSupport } from "@/lib/api";
import { analyzeDurations, isBrandFeedbackColumn, isMultilineColumn } from "@/lib/scriptEditor";
import type { HunkDecision, ModificationSchemeHunk, Script, ScriptColumn } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

const MIN_COLUMN_WIDTH = 88;
const MIN_ROW_HEIGHT = 38;

const COLUMN_HEADER_LABELS: Record<string, string> = {
  duration: "Duration",
  scene: "Visual",
  format: "Format / Script",
  notes: "Remarks",
  feedback: "Brand Feedback"
};

function columnHeaderLabel(column: ScriptColumn) {
  return COLUMN_HEADER_LABELS[column.key] ?? column.label;
}

export function ScriptGrid({
  script,
  mode = "creator",
  onUpdateCell
}: {
  script: Script;
  mode?: "creator" | "share";
  onUpdateCell?: (rowId: string, columnId: string, value: string) => void;
}) {
  if (mode === "share") {
    return <ScriptGridBody mode="share" onUpdateCell={onUpdateCell} script={script} />;
  }
  return <ScriptGridWithHunks script={script} />;
}

function ScriptGridWithHunks({ script }: { script: Script }) {
  const hunkState = useCellHunkMap();
  return <ScriptGridBody hunkState={hunkState} mode="creator" script={script} />;
}

function ScriptGridBody({
  script,
  mode = "creator",
  onUpdateCell,
  hunkState
}: {
  script: Script;
  mode?: "creator" | "share";
  onUpdateCell?: (rowId: string, columnId: string, value: string) => void;
  hunkState?: ReturnType<typeof useCellHunkMap>;
}) {
  const isShare = mode === "share";
  const {
    deleteColumn,
    deleteRow,
    insertColumnAfter,
    insertRowAfter,
    openCoordinatorWithQuote,
    project,
    renameColumn,
    setProject,
    updateCell: storeUpdateCell
  } = useAppStore();
  const updateCell = isShare && onUpdateCell ? onUpdateCell : storeUpdateCell;
  const [quoteMenu, setQuoteMenu] = useState<{ x: number; y: number; rowId: string; columnId: string; text: string } | null>(null);
  const [selectedColumnId, setSelectedColumnId] = useState<string | null>(null);
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const [rowHeights, setRowHeights] = useState<Record<string, number>>({});
  const [argueBusyRowId, setArgueBusyRowId] = useState<string | null>(null);

  const communicationSupportRowIds = useMemo(() => {
    const queue = new Set(project?.communication_support_queue ?? []);
    const ids = new Set<string>();
    for (const node of project?.rationale_nodes ?? []) {
      if (node.source_type !== "brand_feedback") continue;
      const inList = Boolean(node.in_communication_support_queue) || queue.has(node.node_id);
      if (!inList) continue;
      for (const ref of node.linked_script_refs ?? []) {
        if (ref.row_id) ids.add(ref.row_id);
      }
    }
    return ids;
  }, [project?.rationale_nodes, project?.communication_support_queue]);

  async function handleToggleArgue(rowId: string, columnId: string) {
    if (!project || argueBusyRowId) return;
    const nextInList = !communicationSupportRowIds.has(rowId);
    setArgueBusyRowId(rowId);
    try {
      const updated = await toggleCommunicationSupport(project._id, project.user_id, rowId, columnId, nextInList);
      setProject(updated);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Failed to update communication support list");
    } finally {
      setArgueBusyRowId(null);
    }
  }

  const columns = [...script.columns].sort((a, b) => a.order - b.order);
  const rows = [...script.rows].sort((a, b) => a.order - b.order);
  const durationAnalysis = useMemo(() => analyzeDurations(script), [script]);
  const { durationIssueByRowId, linkedIssueByRowId } = useMemo(() => {
    const durationIssueByRowId = new Map<string, string[]>();
    const linkedIssueByRowId = new Map<string, string[]>();

    for (const issue of durationAnalysis.issues) {
      for (const rowId of issue.rowIds) {
        durationIssueByRowId.set(rowId, [
          ...(durationIssueByRowId.get(rowId) ?? []),
          issue.range ? `${issue.message} ${issue.range}` : issue.message
        ]);
      }
    }

    for (const node of project?.rationale_nodes ?? []) {
      for (const ref of node.linked_script_refs ?? []) {
        if (!ref.row_id) continue;
        linkedIssueByRowId.set(ref.row_id, [...(linkedIssueByRowId.get(ref.row_id) ?? []), node.title]);
      }
    }

    return { durationIssueByRowId, linkedIssueByRowId };
  }, [durationAnalysis.issues, project?.rationale_nodes]);
  const totalSeconds = Math.max(0, ...durationAnalysis.timeline.map((segment) => segment.end));
  const {
    hunkByCell,
    hunkDecisions,
    acceptAndApplyHunk,
    rejectAndPersistHunk,
    applyError
  } = hunkState ?? {
    hunkByCell: new Map<string, ModificationSchemeHunk>(),
    hunkDecisions: {} as Record<string, HunkDecision>,
    acceptAndApplyHunk: async () => undefined,
    rejectAndPersistHunk: async () => undefined,
    applyError: null as string | null
  };

  useEffect(() => {
    function handleDocumentPointerDown(event: globalThis.MouseEvent) {
      const target = event.target as HTMLElement;
      if (target.closest(".editor-th-data")) return;
      setSelectedColumnId(null);
    }

    document.addEventListener("mousedown", handleDocumentPointerDown);
    return () => document.removeEventListener("mousedown", handleDocumentPointerDown);
  }, []);

  function handleAddColumn(afterColumnId?: string) {
    insertColumnAfter(afterColumnId, "New Column", false);
  }

  function handleRenameColumn(columnId: string, currentLabel: string) {
    const column = columns.find((item) => item.column_id === columnId);
    if (column && isBrandFeedbackColumn(column)) {
      window.alert("The Brand Feedback column cannot be renamed. Brand partners fill it on the share page.");
      return;
    }
    const label = window.prompt("Rename column", currentLabel)?.trim();
    if (!label || label === currentLabel) return;
    renameColumn(columnId, label);
  }

  function handleDeleteColumn(columnId: string) {
    const column = columns.find((item) => item.column_id === columnId);
    if (column && isBrandFeedbackColumn(column)) {
      window.alert("The Brand Feedback column cannot be deleted.");
      return;
    }
    if (!window.confirm("Delete this column? Cell values in this column will be removed.")) return;
    try {
      deleteColumn(columnId);
      setSelectedColumnId(null);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Delete failed");
    }
  }

  function handleDeleteRow(rowId: string) {
    if (!window.confirm("Delete this row?")) return;
    try {
      deleteRow(rowId);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Delete failed");
    }
  }

  function handleSelection(event: MouseEvent<HTMLElement>, rowId: string, columnId: string) {
    const selectedText = window.getSelection()?.toString().trim();
    if (!selectedText) {
      setQuoteMenu(null);
      return;
    }
    setQuoteMenu({ x: event.clientX, y: event.clientY, rowId, columnId, text: selectedText });
  }

  function quoteToCoordinator() {
    if (!quoteMenu) return;
    openCoordinatorWithQuote({
      rowId: quoteMenu.rowId,
      columnId: quoteMenu.columnId,
      text: quoteMenu.text
    });
    setQuoteMenu(null);
  }

  async function addSelectionToGraph() {
    if (!quoteMenu || !project) return;
    try {
      const updated = await createGraphNode(project._id, project.user_id, {
        node_type: "issue",
        title: quoteMenu.text.slice(0, 80),
        content: quoteMenu.text,
        source_type: "creator_manual",
        linked_script_refs: [
          {
            row_id: quoteMenu.rowId,
            column_id: quoteMenu.columnId,
            text_snapshot: quoteMenu.text
          }
        ]
      });
      setProject(updated);
      setQuoteMenu(null);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Failed to add Issue to graph");
    }
  }

  function startColumnResize(event: PointerEvent<HTMLElement>, columnId: string) {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = columnWidths[columnId] ?? event.currentTarget.parentElement?.getBoundingClientRect().width ?? MIN_COLUMN_WIDTH;

    function handleMove(moveEvent: globalThis.PointerEvent) {
      setColumnWidths((current) => ({
        ...current,
        [columnId]: Math.max(MIN_COLUMN_WIDTH, startWidth + moveEvent.clientX - startX)
      }));
    }

    function handleUp() {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
  }

  function startRowResize(event: PointerEvent<HTMLElement>, rowId: string) {
    event.preventDefault();
    event.stopPropagation();
    const startY = event.clientY;
    const rowElement = event.currentTarget.closest("tr")?.previousElementSibling as HTMLTableRowElement | null;
    const startHeight = rowHeights[rowId] ?? rowElement?.getBoundingClientRect().height ?? MIN_ROW_HEIGHT;

    function handleMove(moveEvent: globalThis.PointerEvent) {
      setRowHeights((current) => ({
        ...current,
        [rowId]: Math.max(MIN_ROW_HEIGHT, startHeight + moveEvent.clientY - startY)
      }));
    }

    function handleUp() {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
    }

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
  }

  function handleAddSceneBlock() {
    insertRowAfter(rows.at(-1)?.row_id);
  }

  return (
    <div className={`editor-wrap${isShare ? " editor-wrap--share" : ""}`}>
      {!isShare ? (
        <div className="script-timeline-wrap" aria-label="Script duration timeline">
          <div className="script-timeline-row">
            <span className="script-timeline-label">Duration</span>
            <div className="script-timeline-track">
              {durationAnalysis.timeline.map((segment, index) => (
                <span
                  className={`script-timeline-segment${segment.hasOverlap ? " script-timeline-segment--overlap" : ""}`}
                  key={segment.rowId}
                  style={{ left: `${segment.left}%`, width: `${Math.max(segment.width, 0.8)}%` }}
                  title={`#${index + 1}: ${segment.start}–${segment.end}s`}
                />
              ))}
              {durationAnalysis.overlaps.map((overlap) => (
                <span
                  className="script-timeline-overlap"
                  key={`${overlap.start}-${overlap.end}`}
                  style={{ left: `${overlap.left}%`, width: `${Math.max(overlap.width, 2)}%` }}
                  title={`Overlap ${overlap.start}-${overlap.end}s`}
                />
              ))}
            </div>
            <span className="script-timeline-total">{formatClock(totalSeconds)}</span>
          </div>
          {durationAnalysis.issues.length ? (
            <div className="script-timeline-alert show">
              {durationAnalysis.issues.map((issue) => (issue.range ? `${issue.message} ${issue.range}` : issue.message)).join(" / ")}
            </div>
          ) : null}
        </div>
      ) : null}

      {!isShare && applyError ? <p className="editor-hunk-apply-error">{applyError}</p> : null}

      <div className="script-table-container">
        <div className="script-table-panel">
          <table className="editor-data-table">
            <thead>
              <tr>
                <th className="editor-th-num col-num">
                  #
                  {!isShare ? (
                    <button
                      className="editor-col-insert-hit editor-col-insert-first"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleAddColumn(undefined);
                      }}
                      type="button"
                      title="Insert column before first"
                    >
                      +
                    </button>
                  ) : null}
                </th>
                {columns.map((column, columnIndex) => (
                  <th
                    className={`editor-th-data col-${column.key} ${!isShare && selectedColumnId === column.column_id ? "col-selected" : ""}`}
                    key={column.column_id}
                    onClick={
                      isShare
                        ? undefined
                        : (event) => {
                            event.stopPropagation();
                            setSelectedColumnId((current) => (current === column.column_id ? null : column.column_id));
                            setSelectedRowId(null);
                          }
                    }
                    style={{ width: columnWidths[column.column_id] }}
                  >
                    <span
                      className="editor-th-label"
                      onDoubleClick={isShare ? undefined : () => handleRenameColumn(column.column_id, column.label)}
                    >
                      {columnHeaderLabel(column)}
                    </span>
                    {!isShare ? (
                      <>
                        <button
                          className="editor-col-insert-hit"
                          onClick={(event) => {
                            event.stopPropagation();
                            handleAddColumn(columns[columnIndex - 1]?.column_id);
                          }}
                          type="button"
                          title="Insert column to the left"
                        >
                          +
                        </button>
                        {columnIndex === columns.length - 1 ? (
                          <button
                            className="editor-col-insert-hit editor-col-insert-last"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleAddColumn(column.column_id);
                            }}
                            type="button"
                            title="Append column at end"
                          >
                            +
                          </button>
                        ) : null}
                        <span className="editor-col-resize-hit" onPointerDown={(event) => startColumnResize(event, column.column_id)} />
                        {isBrandFeedbackColumn(column) ? null : (
                          <button
                            className="editor-col-del"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDeleteColumn(column.column_id);
                            }}
                            type="button"
                          >
                            Delete column
                          </button>
                        )}
                      </>
                    ) : (
                      <span className="editor-col-resize-hit" onPointerDown={(event) => startColumnResize(event, column.column_id)} />
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!isShare ? (
                <tr className="editor-row-insert-band editor-row-insert-first">
                  <td className="editor-row-insert-cell" colSpan={columns.length + 1}>
                    <span className="editor-row-insert-line" />
                    <button className="editor-row-insert-btn" onClick={() => insertRowAfter(undefined)} type="button">
                      +
                      <span className="editor-row-insert-tip">Insert row before first</span>
                    </button>
                  </td>
                </tr>
              ) : null}
              {rows.map((row, rowIndex) => (
                <RowBlock
                  columns={columns}
                  columnWidths={columnWidths}
                  argueBusy={!isShare && argueBusyRowId === row.row_id}
                  durationIssueMessages={isShare ? undefined : durationIssueByRowId.get(row.row_id)}
                  feedbackArgued={!isShare && communicationSupportRowIds.has(row.row_id)}
                  hunkByCell={hunkByCell}
                  hunkDecisions={hunkDecisions}
                  index={rowIndex}
                  key={row.row_id}
                  linkedIssueMessages={isShare ? undefined : linkedIssueByRowId.get(row.row_id)}
                  mode={mode}
                  onToggleArgue={isShare ? undefined : handleToggleArgue}
                  onAddRow={() => insertRowAfter(row.row_id)}
                  onDeleteRow={() => handleDeleteRow(row.row_id)}
                  onHunkAccept={(hunkId) => void acceptAndApplyHunk(hunkId)}
                  onHunkReject={(hunkId) => void rejectAndPersistHunk(hunkId)}
                  onResizeRow={(event) => startRowResize(event, row.row_id)}
                  onSelection={handleSelection}
                  onSelectRow={() => {
                    setSelectedRowId(row.row_id);
                    setSelectedColumnId(null);
                  }}
                  row={row}
                  rowHeight={rowHeights[row.row_id]}
                  selected={!isShare && selectedRowId === row.row_id}
                  updateCell={updateCell}
                />
              ))}
              {!isShare ? (
                <tr className="editor-row-insert-band">
                  <td className="editor-row-insert-cell" colSpan={columns.length + 1}>
                    <span className="editor-row-insert-line" />
                    <button className="editor-row-insert-btn" onClick={() => insertRowAfter(rows.at(-1)?.row_id)} type="button">
                      +
                      <span className="editor-row-insert-tip">Insert row</span>
                    </button>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        {!isShare ? (
          <div className="script-table-footer">
            <button className="add-scene-block-btn" onClick={handleAddSceneBlock} type="button">
              <IconAddScene />
              Add New Scene Block
            </button>
          </div>
        ) : null}
      </div>

      {!isShare && quoteMenu ? (
        <div className="sel-popup show" style={{ left: quoteMenu.x, top: quoteMenu.y }}>
          <button className="sel-btn sel-btn-coordinator" onClick={quoteToCoordinator} type="button">
            Ask Coordinator
          </button>
          <button className="sel-btn sel-btn-graph" onClick={() => void addSelectionToGraph()} type="button">
            Add as Issue
          </button>
        </div>
      ) : null}
    </div>
  );
}

function formatRowHint(durationIssueMessages?: string[], linkedIssueMessages?: string[]) {
  const parts: string[] = [];
  if (durationIssueMessages?.length) {
    parts.push(`Duration: ${durationIssueMessages.join(" / ")}`);
  }
  if (linkedIssueMessages?.length) {
    parts.push(`Map: ${linkedIssueMessages.join(" / ")}`);
  }
  return parts.length ? parts.join("\n") : undefined;
}

function RowBlock({
  argueBusy = false,
  columns,
  columnWidths,
  durationIssueMessages,
  feedbackArgued = false,
  hunkByCell,
  hunkDecisions,
  index,
  linkedIssueMessages,
  mode = "creator",
  onAddRow,
  onDeleteRow,
  onHunkAccept,
  onHunkReject,
  onResizeRow,
  onSelection,
  onSelectRow,
  onToggleArgue,
  row,
  rowHeight,
  selected,
  updateCell
}: {
  argueBusy?: boolean;
  columns: Script["columns"];
  columnWidths: Record<string, number>;
  durationIssueMessages?: string[];
  feedbackArgued?: boolean;
  hunkByCell: Map<string, ModificationSchemeHunk>;
  hunkDecisions: Record<string, HunkDecision>;
  index: number;
  linkedIssueMessages?: string[];
  mode?: "creator" | "share";
  onAddRow: () => void;
  onDeleteRow: () => void;
  onHunkAccept: (hunkId: string) => void;
  onHunkReject: (hunkId: string) => void;
  onResizeRow: (event: PointerEvent<HTMLElement>) => void;
  onSelection: (event: MouseEvent<HTMLElement>, rowId: string, columnId: string) => void;
  onSelectRow: () => void;
  onToggleArgue?: (rowId: string, columnId: string) => void;
  row: Script["rows"][number];
  rowHeight?: number;
  selected: boolean;
  updateCell: (rowId: string, columnId: string, value: string) => void;
}) {
  const isShare = mode === "share";
  const rowMark = String(index + 1).padStart(2, "0");
  const hasDurationIssue = Boolean(durationIssueMessages?.length);
  const hasLinkedIssue = Boolean(linkedIssueMessages?.length);
  const rowHintTitle = formatRowHint(durationIssueMessages, linkedIssueMessages);

  return (
    <>
      <tr
        className={`editor-row ${index % 2 === 1 ? "row-alt" : ""} ${hasDurationIssue ? "row-has-duration-issue" : ""} ${hasLinkedIssue ? "row-has-linked-issue" : ""} ${selected ? "row-selected" : ""}`}
        style={{ height: rowHeight }}
      >
        <td className="editor-td-num" title={rowHintTitle}>
          {hasLinkedIssue ? <span aria-hidden="true" className="editor-row-link-mark" title="Linked to Map issue" /> : null}
          {isShare ? (
            <span className="editor-row-num-btn editor-row-num-btn--static">{rowMark}</span>
          ) : (
            <>
              <button className="editor-row-num-btn" onClick={onSelectRow} type="button">
                {rowMark}
              </button>
              <button className="editor-row-del editor-row-del-left" onClick={onDeleteRow} type="button" title="Delete row">
                <IconTrash />
              </button>
            </>
          )}
        </td>
        {columns.map((column) => {
          const value = row.cells.find((cell) => cell.column_id === column.column_id)?.value ?? "";
          const brandFeedback = isBrandFeedbackColumn(column);
          const hunk = hunkByCell.get(`${row.row_id}:${column.column_id}`);
          const hunkDecision = hunk ? (hunkDecisions[hunk.hunk_id] ?? null) : null;
          const showHunkDiff = Boolean(hunk && hunkDecision === null);
          const cellReadOnly = isShare ? !brandFeedback : brandFeedback;

          const commonProps = {
            value,
            onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
              updateCell(row.row_id, column.column_id, event.target.value),
            onMouseUp: isShare ? undefined : (event: MouseEvent<HTMLElement>) => onSelection(event, row.row_id, column.column_id),
            placeholder: brandFeedback
              ? isShare
                ? "Enter your feedback for this scene"
                : "Filled by brand partner via share link"
              : column.type === "duration"
                ? "0-5"
                : "",
            readOnly: cellReadOnly,
            title: brandFeedback
              ? isShare
                ? "Brand feedback — your comments are saved automatically"
                : "Brand feedback (read-only). Synced from the share page."
              : isShare
                ? "Read-only"
                : undefined,
            style: { minHeight: rowHeight ? Math.max(MIN_ROW_HEIGHT, rowHeight) : undefined }
          };

          return (
            <td
              className={[
                `editor-td-data col-${column.key}`,
                brandFeedback ? "col-brand-feedback" : "",
                showHunkDiff ? "editor-td-has-hunk" : ""
              ]
                .filter(Boolean)
                .join(" ")}
              key={column.column_id}
              style={{ width: columnWidths[column.column_id] }}
            >
              {showHunkDiff && hunk ? (
                <CellHunkDiff
                  decision={hunkDecision}
                  hunk={hunk}
                  onAccept={() => onHunkAccept(hunk.hunk_id)}
                  onReject={() => onHunkReject(hunk.hunk_id)}
                />
              ) : column.type === "duration" ? (
                <div className="editor-duration-wrap">
                  <input className={`editor-table-input editor-duration-input ${hasDurationIssue ? "is-invalid" : ""}`} {...commonProps} />
                </div>
              ) : isMultilineColumn(column) ? (
                <textarea
                  className={`editor-table-cell cell-${column.key}${cellReadOnly ? " editor-table-cell--readonly" : ""}`}
                  {...commonProps}
                />
              ) : (
                <input
                  className={`editor-table-input cell-${column.key}${cellReadOnly ? " editor-table-input--readonly" : ""}`}
                  {...commonProps}
                />
              )}
              {brandFeedback && !isShare && value.trim() && onToggleArgue ? (
                <button
                  className={`feedback-argue-btn${feedbackArgued ? " is-active" : ""}`}
                  onClick={() => onToggleArgue(row.row_id, column.column_id)}
                  disabled={argueBusy}
                  type="button"
                  title={
                    feedbackArgued
                      ? "On your communication support list — click to remove"
                      : "Argue this feedback (add to communication support list)"
                  }
                >
                  {argueBusy ? "…" : feedbackArgued ? "Arguing ✓" : "Argue"}
                </button>
              ) : null}
            </td>
          );
        })}
      </tr>
      {!isShare ? (
        <tr className="editor-row-insert-band">
          <td className="editor-row-insert-cell" colSpan={columns.length + 1}>
            <span className="editor-row-insert-line" />
            <span className="editor-row-resize-hit" onPointerDown={onResizeRow} title="Drag to resize row height" />
            <button className="editor-row-insert-btn" onClick={onAddRow} type="button">
              +
              <span className="editor-row-insert-tip">Insert row below</span>
            </button>
          </td>
        </tr>
      ) : null}
    </>
  );
}

function formatClock(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function IconAddScene() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect height="18" rx="2" width="14" x="5" y="3" />
      <line x1="12" x2="12" y1="8" y2="16" />
      <line x1="8" x2="16" y1="12" y2="12" />
    </svg>
  );
}

function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}
