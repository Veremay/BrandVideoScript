"use client";

import { PointerEvent, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { CellHunkDiff, useCellHunkMap } from "@/components/ScriptCellModification";
import { toggleCommunicationSupport } from "@/lib/api";
import { analyzeDurations, durationInputValue, isBrandFeedbackColumn } from "@/lib/scriptEditor";
import type { HunkDecision, ModificationSchemeHunk, Script } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

const MIN_COLUMN_WIDTH = 88;
const INSERTED_COLUMN_MIN_WIDTH = 160;
const MIN_ROW_HEIGHT = 38;
const COLUMN_WIDTH_STORAGE_PREFIX = "brandvideo:script-column-widths:";
const DEFAULT_COLUMN_LABELS: Record<string, string> = {
  duration: "Duration (s)",
  scene: "Visual",
  format: "Format / Script",
  notes: "Remarks",
  feedback: "Brand Feedback"
};
const LEGACY_DEFAULT_COLUMN_LABELS: Record<string, string[]> = {
  duration: ["时长", "Seconds"],
  scene: ["画面"],
  format: ["形式"],
  notes: ["备注"],
  feedback: ["品牌反馈"]
};

function displayedColumnLabel(column: { key: string; label: string }) {
  return LEGACY_DEFAULT_COLUMN_LABELS[column.key]?.includes(column.label)
    ? DEFAULT_COLUMN_LABELS[column.key] ?? column.label
    : column.label;
}

function AutoSizeTextarea({
  className,
  minHeight,
  onChange,
  style,
  ...props
}: React.ComponentProps<"textarea"> & { minHeight?: number }) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const syncHeight = useCallback(() => {
    const node = ref.current;
    if (!node) return;
    const cssMinHeight = Number.parseFloat(
      getComputedStyle(node).getPropertyValue("--script-cell-min-height")
    );
    const effectiveMinHeight = minHeight ?? (Number.isFinite(cssMinHeight) ? cssMinHeight : MIN_ROW_HEIGHT);
    node.style.height = "0px";
    node.style.height = `${Math.max(effectiveMinHeight, node.scrollHeight)}px`;
  }, [minHeight]);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    syncHeight();
    let observedWidth = node.getBoundingClientRect().width;
    let resizeTimer: number | undefined;
    let fontSizeFrame: number | undefined;
    const observer = new ResizeObserver((entries) => {
      const nextWidth = entries[0]?.contentRect.width;
      // Height changes also notify ResizeObserver. React only to a real width
      // change so resetting the textarea height cannot create an observer loop.
      if (nextWidth === undefined || Math.abs(nextWidth - observedWidth) < 0.5) return;
      observedWidth = nextWidth;
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(syncHeight, 50);
    });
    observer.observe(node);
    const appRoot = node.closest(".app-figma");
    const fontSizeObserver = appRoot
      ? new MutationObserver((mutations) => {
          if (mutations.some((mutation) => mutation.attributeName === "data-font-size")) {
            if (fontSizeFrame !== undefined) window.cancelAnimationFrame(fontSizeFrame);
            fontSizeFrame = window.requestAnimationFrame(syncHeight);
          }
        })
      : null;
    fontSizeObserver?.observe(appRoot!, { attributes: true, attributeFilter: ["data-font-size"] });

    return () => {
      observer.disconnect();
      fontSizeObserver?.disconnect();
      window.clearTimeout(resizeTimer);
      if (fontSizeFrame !== undefined) window.cancelAnimationFrame(fontSizeFrame);
    };
  }, [props.value, syncHeight, className, minHeight]);

  return (
    <textarea
      ref={ref}
      rows={1}
      className={className}
      style={{ ...style, ...(minHeight === undefined ? {} : { minHeight }), overflow: "hidden", resize: "none" }}
      onChange={(event) => {
        onChange?.(event);
        syncHeight();
      }}
      {...props}
    />
  );
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
    project,
    renameColumn,
    setProject,
    setMapFocusNodeId,
    setWorkspaceView,
    undoScript,
    updateCell: storeUpdateCell
  } = useAppStore();
  const updateCell = isShare && onUpdateCell ? onUpdateCell : storeUpdateCell;
  const [selectedColumnId, setSelectedColumnId] = useState<string | null>(null);
  const [editingColumnId, setEditingColumnId] = useState<string | null>(null);
  const [editingColumnLabel, setEditingColumnLabel] = useState("");
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const [rowHeights, setRowHeights] = useState<Record<string, number>>({});
  const [argueBusyRowId, setArgueBusyRowId] = useState<string | null>(null);
  const [activeEditingRowId, setActiveEditingRowId] = useState<string | null>(null);
  const tableRef = useRef<HTMLTableElement>(null);
  const pendingColumnWidthsRef = useRef<Record<string, number> | null>(null);

  const communicationSupportRowIds = useMemo(() => {
    const queueItems = project?.communication_support_queue ?? [];
    const queue = new Set(queueItems);
    const ids = new Set<string>(queueItems);
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

  const columns = useMemo(() => [...script.columns].sort((a, b) => a.order - b.order), [script.columns]);
  const rows = useMemo(() => [...script.rows].sort((a, b) => a.order - b.order), [script.rows]);
  const columnIdSignature = columns.map((column) => column.column_id).join("|");

  useEffect(() => {
    if (isShare) return;
    for (const column of columns) {
      const englishLabel = DEFAULT_COLUMN_LABELS[column.key];
      if (englishLabel && LEGACY_DEFAULT_COLUMN_LABELS[column.key]?.includes(column.label)) {
        renameColumn(column.column_id, englishLabel, false);
      }
    }
  }, [columnIdSignature, isShare, project?._id, renameColumn]);

  useEffect(() => {
    if (isShare || !project?._id) return;
    const pendingWidths = pendingColumnWidthsRef.current;
    if (pendingWidths && columns.every((column) => Number.isFinite(pendingWidths[column.column_id]))) {
      pendingColumnWidthsRef.current = null;
      setColumnWidths(pendingWidths);
      return;
    }
    try {
      const saved = window.localStorage.getItem(`${COLUMN_WIDTH_STORAGE_PREFIX}${project._id}`);
      if (!saved) {
        setColumnWidths({});
        return;
      }
      const parsed = JSON.parse(saved) as Record<string, unknown>;
      const restored: Record<string, number> = {};
      for (const column of columns) {
        const width = parsed[column.column_id];
        if (typeof width !== "number" || !Number.isFinite(width) || width < MIN_COLUMN_WIDTH) {
          setColumnWidths({});
          return;
        }
        restored[column.column_id] = width;
      }
      setColumnWidths(restored);
    } catch {
      setColumnWidths({});
    }
  }, [columnIdSignature, isShare, project?._id]);

  function clearSavedColumnWidths() {
    setColumnWidths({});
    if (!isShare && project?._id) {
      try {
        window.localStorage.removeItem(`${COLUMN_WIDTH_STORAGE_PREFIX}${project._id}`);
      } catch {
        // The table still resets when browser storage is unavailable.
      }
    }
  }
  const durationAnalysis = useMemo(() => analyzeDurations(script), [script]);
  const { durationIssueByRowId, durationSegmentByRowId, linkedNodeByRowId } = useMemo(() => {
    const durationIssueByRowId = new Map<string, string[]>();
    const durationSegmentByRowId = new Map(durationAnalysis.timeline.map((segment) => [segment.rowId, segment]));
    const linkedNodeByRowId = new Map<string, Array<{ nodeId: string; title: string }>>();

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
        linkedNodeByRowId.set(ref.row_id, [
          ...(linkedNodeByRowId.get(ref.row_id) ?? []),
          { nodeId: node.node_id, title: node.title }
        ]);
      }
    }

    return { durationIssueByRowId, durationSegmentByRowId, linkedNodeByRowId };
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

  useEffect(() => {
    if (isShare) return;

    function handleUndoShortcut(event: KeyboardEvent) {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey || event.key.toLowerCase() !== "z") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target?.closest(".editor-th-label-input")) return;
      const isEditableTarget = target?.matches("input, textarea, [contenteditable='true']") ?? false;
      if (isEditableTarget && !target?.closest(".script-table-container")) return;

      event.preventDefault();
      undoScript();
    }

    window.addEventListener("keydown", handleUndoShortcut);
    return () => window.removeEventListener("keydown", handleUndoShortcut);
  }, [isShare, undoScript]);

  function handleAddColumn(afterColumnId?: string) {
    const existingWidths = Object.fromEntries(
      Array.from(tableRef.current?.querySelectorAll<HTMLTableCellElement>("th[data-column-id]") ?? []).map(
        (header) => [header.dataset.columnId!, header.getBoundingClientRect().width]
      )
    );
    const existingColumnIds = new Set(columns.map((column) => column.column_id));
    clearSavedColumnWidths();
    insertColumnAfter(afterColumnId, "New Column", false);
    const insertedColumn = useAppStore
      .getState()
      .script?.columns.find((column) => !existingColumnIds.has(column.column_id));
    if (insertedColumn) {
      const nextWidths = {
        ...existingWidths,
        [insertedColumn.column_id]: INSERTED_COLUMN_MIN_WIDTH
      };
      pendingColumnWidthsRef.current = nextWidths;
      setColumnWidths(nextWidths);
      if (!isShare && project?._id) {
        try {
          window.localStorage.setItem(
            `${COLUMN_WIDTH_STORAGE_PREFIX}${project._id}`,
            JSON.stringify(nextWidths)
          );
        } catch {
          // The inserted column still keeps its width for the current session.
        }
      }
    }
  }

  function startColumnRename(columnId: string, currentLabel: string) {
    const column = columns.find((item) => item.column_id === columnId);
    if (column && isBrandFeedbackColumn(column)) {
      window.alert("The Brand Feedback column cannot be renamed. Brand partners fill it on the share page.");
      return;
    }
    setEditingColumnId(columnId);
    setEditingColumnLabel(currentLabel);
  }

  function commitColumnRename(columnId: string) {
    const label = editingColumnLabel.trim();
    const currentLabel = columns.find((column) => column.column_id === columnId)?.label;
    setEditingColumnId(null);
    if (!label || label === currentLabel) return;
    renameColumn(columnId, label);
  }

  function handleDeleteColumn(columnId: string) {
    const columnIndex = columns.findIndex((item) => item.column_id === columnId);
    const column = columns[columnIndex];
    if (column?.key === "duration") {
      window.alert("The Duration column cannot be deleted.");
      return;
    }
    if (column && isBrandFeedbackColumn(column)) {
      window.alert("The Brand Feedback column cannot be deleted.");
      return;
    }
    if (!window.confirm("Delete this column? Cell values in this column will be removed.")) return;
    try {
      const existingWidths = Object.fromEntries(
        Array.from(tableRef.current?.querySelectorAll<HTMLTableCellElement>("th[data-column-id]") ?? []).map(
          (header) => [header.dataset.columnId!, header.getBoundingClientRect().width]
        )
      );
      const deletedWidth = existingWidths[columnId] ?? columnWidths[columnId] ?? MIN_COLUMN_WIDTH;
      const widthReceiver = columns[columnIndex + 1] ?? columns[columnIndex - 1];
      const nextWidths = Object.fromEntries(
        Object.entries(existingWidths).filter(([existingColumnId]) => existingColumnId !== columnId)
      );
      if (widthReceiver) {
        nextWidths[widthReceiver.column_id] =
          (nextWidths[widthReceiver.column_id] ?? columnWidths[widthReceiver.column_id] ?? MIN_COLUMN_WIDTH) + deletedWidth;
      }

      deleteColumn(columnId);
      pendingColumnWidthsRef.current = nextWidths;
      setColumnWidths(nextWidths);
      if (!isShare && project?._id) {
        try {
          window.localStorage.setItem(
            `${COLUMN_WIDTH_STORAGE_PREFIX}${project._id}`,
            JSON.stringify(nextWidths)
          );
        } catch {
          // The adjusted widths still remain active for the current session.
        }
      }
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

  function startColumnResize(event: PointerEvent<HTMLElement>, columnId: string) {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const headerRow = event.currentTarget.closest("tr");
    const headerCells = Array.from(headerRow?.querySelectorAll<HTMLTableCellElement>("th[data-column-id]") ?? []);
    const lockedWidths = Object.fromEntries(
      headerCells.map((header) => [header.dataset.columnId!, header.getBoundingClientRect().width])
    );
    const startWidth = lockedWidths[columnId] ?? event.currentTarget.parentElement?.getBoundingClientRect().width ?? MIN_COLUMN_WIDTH;

    // Freeze every current column width before resizing. Otherwise a fixed-layout
    // 100%-wide table redistributes the delta across neighbouring columns.
    setColumnWidths(lockedWidths);
    let latestWidths = lockedWidths;

    function handleMove(moveEvent: globalThis.PointerEvent) {
      latestWidths = {
        ...lockedWidths,
        [columnId]: Math.max(MIN_COLUMN_WIDTH, startWidth + moveEvent.clientX - startX)
      };
      setColumnWidths(latestWidths);
    }

    function handleUp() {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      window.removeEventListener("pointercancel", handleUp);
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
      if (!isShare && project?._id) {
        try {
          window.localStorage.setItem(
            `${COLUMN_WIDTH_STORAGE_PREFIX}${project._id}`,
            JSON.stringify(latestWidths)
          );
        } catch {
          // Resizing remains functional when browser storage is unavailable.
        }
      }
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    window.addEventListener("pointercancel", handleUp);
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

  const hasLockedColumnWidths = columns.every((column) => Number.isFinite(columnWidths[column.column_id]));
  const lockedTableWidth = hasLockedColumnWidths
    ? 64 + columns.reduce((total, column) => total + columnWidths[column.column_id], 0)
    : undefined;

  return (
    <div className={`editor-wrap${isShare ? " editor-wrap--share" : ""}`}>
      {!isShare ? (
        <div className="script-timeline-wrap" aria-label="Script duration timeline">
          <div className="script-timeline-row">
            <span className="script-timeline-label">Duration</span>
            <div className="script-timeline-track">
              {durationAnalysis.timeline.map((segment, index) => (
                <span
                  className={`script-timeline-segment${segment.hasOverlap ? " script-timeline-segment--overlap" : ""}${activeEditingRowId === segment.rowId ? " script-timeline-segment--active" : ""}`}
                  key={segment.rowId}
                  style={{ left: `${segment.left}%`, width: `${Math.max(segment.width, 0.8)}%` }}
                  title={`#${index + 1}: ${formatClock(segment.start)}–${formatClock(segment.end)}`}
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
        <div className="script-table-panel app-scrollbar">
          <table
            className="editor-data-table"
            ref={tableRef}
            style={lockedTableWidth === undefined ? undefined : { minWidth: lockedTableWidth, width: lockedTableWidth }}
          >
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
                      title="Insert column"
                    >
                      +
                    </button>
                  ) : null}
                </th>
                {columns.map((column, columnIndex) => (
                  <th
                    className={`editor-th-data col-${column.key} ${!isShare && selectedColumnId === column.column_id ? "col-selected" : ""}`}
                    data-column-id={column.column_id}
                    key={column.column_id}
                    onClick={
                      isShare
                        ? undefined
                        : (event) => {
                            event.stopPropagation();
                            setSelectedColumnId(column.column_id);
                            setSelectedRowId(null);
                          }
                    }
                    style={{ width: columnWidths[column.column_id] }}
                  >
                    {editingColumnId === column.column_id ? (
                      <input
                        aria-label="Column name"
                        autoFocus
                        className="editor-th-label-input"
                        onBlur={(event) => {
                          if (event.currentTarget.dataset.cancel !== "true") commitColumnRename(column.column_id);
                        }}
                        onChange={(event) => setEditingColumnLabel(event.target.value)}
                        onClick={(event) => event.stopPropagation()}
                        onDoubleClick={(event) => event.stopPropagation()}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            commitColumnRename(column.column_id);
                          } else if (event.key === "Escape") {
                            event.currentTarget.dataset.cancel = "true";
                            setEditingColumnId(null);
                          }
                        }}
                        value={editingColumnLabel}
                      />
                    ) : (
                      <span
                        className="editor-th-label"
                        onDoubleClick={
                          isShare
                            ? undefined
                            : (event) => {
                                event.stopPropagation();
                                if (selectedColumnId === column.column_id) {
                                  startColumnRename(column.column_id, displayedColumnLabel(column));
                                }
                              }
                        }
                      >
                        {displayedColumnLabel(column)}
                      </span>
                    )}
                    {!isShare ? (
                      <>
                        <button
                          className="editor-col-insert-hit"
                          onClick={(event) => {
                            event.stopPropagation();
                            handleAddColumn(columns[columnIndex - 1]?.column_id);
                          }}
                          type="button"
                          title="Insert column"
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
                        {column.key === "duration" || isBrandFeedbackColumn(column) ? null : (
                          <button
                            className="editor-col-del"
                            aria-label="Delete column"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDeleteColumn(column.column_id);
                            }}
                            title="Delete column"
                            type="button"
                          >
                            <IconTrash />
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
                    <button
                      className="editor-row-insert-btn"
                      onClick={() => insertRowAfter(undefined)}
                      title="Insert row before first"
                      type="button"
                    >
                      +
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
                  durationSegment={durationSegmentByRowId.get(row.row_id)}
                  feedbackArgued={!isShare && communicationSupportRowIds.has(row.row_id)}
                  hunkByCell={hunkByCell}
                  hunkDecisions={hunkDecisions}
                  index={rowIndex}
                  key={row.row_id}
                  linkedNodes={isShare ? undefined : linkedNodeByRowId.get(row.row_id)}
                  mode={mode}
                  onToggleArgue={isShare ? undefined : handleToggleArgue}
                  onAddRow={() => insertRowAfter(row.row_id)}
                  onDeleteRow={() => handleDeleteRow(row.row_id)}
                  onHunkAccept={(hunkId) => void acceptAndApplyHunk(hunkId)}
                  onHunkReject={(hunkId) => void rejectAndPersistHunk(hunkId)}
                  onJumpToNode={(nodeId) => {
                    setMapFocusNodeId(nodeId);
                    setWorkspaceView("map");
                  }}
                  onCellBlur={() => setActiveEditingRowId((current) => (current === row.row_id ? null : current))}
                  onCellFocus={() => setActiveEditingRowId(row.row_id)}
                  onResizeRow={(event) => startRowResize(event, row.row_id)}
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
            </tbody>
          </table>
        </div>
        {/* Temporarily hidden so the table fills the window
        {!isShare ? (
          <div className="script-table-footer">
            <button className="add-scene-block-btn" onClick={handleAddSceneBlock} type="button">
              <IconAddScene />
              Add New Scene Block
            </button>
          </div>
        ) : null}
        */}
      </div>
    </div>
  );
}

function formatRowHint(durationIssueMessages?: string[], linkedNodeTitles?: string[]) {
  const parts: string[] = [];
  if (durationIssueMessages?.length) {
    parts.push(`Duration: ${durationIssueMessages.join(" / ")}`);
  }
  if (linkedNodeTitles?.length) {
    parts.push(`Map: ${linkedNodeTitles.join(" / ")}`);
  }
  return parts.length ? parts.join("\n") : undefined;
}

function RowBlock({
  argueBusy = false,
  columns,
  columnWidths,
  durationIssueMessages,
  durationSegment,
  feedbackArgued = false,
  hunkByCell,
  hunkDecisions,
  index,
  linkedNodes,
  mode = "creator",
  onAddRow,
  onCellBlur,
  onCellFocus,
  onDeleteRow,
  onHunkAccept,
  onHunkReject,
  onJumpToNode,
  onResizeRow,
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
  durationSegment?: { start: number; end: number };
  feedbackArgued?: boolean;
  hunkByCell: Map<string, ModificationSchemeHunk>;
  hunkDecisions: Record<string, HunkDecision>;
  index: number;
  linkedNodes?: Array<{ nodeId: string; title: string }>;
  mode?: "creator" | "share";
  onAddRow: () => void;
  onCellBlur: () => void;
  onCellFocus: () => void;
  onDeleteRow: () => void;
  onHunkAccept: (hunkId: string) => void;
  onHunkReject: (hunkId: string) => void;
  onJumpToNode?: (nodeId: string) => void;
  onResizeRow: (event: PointerEvent<HTMLElement>) => void;
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
  const linkedNodeTitles = linkedNodes?.map((node) => node.title) ?? [];
  const firstLinkedNodeId = linkedNodes?.[0]?.nodeId;
  const hasLinkedIssue = Boolean(linkedNodes?.length);
  const rowHintTitle = formatRowHint(durationIssueMessages, linkedNodeTitles);

  return (
    <>
      <tr
        className={`editor-row ${index % 2 === 1 ? "row-alt" : ""} ${hasDurationIssue ? "row-has-duration-issue" : ""} ${hasLinkedIssue ? "row-has-linked-issue" : ""} ${selected ? "row-selected" : ""}`}
      >
        <td className="editor-td-num" title={rowHintTitle}>
          {firstLinkedNodeId && onJumpToNode ? (
            <button
              aria-label={`Open related Map node for row ${rowMark}`}
              className="editor-row-link-mark"
              onClick={(event) => {
                event.stopPropagation();
                onJumpToNode(firstLinkedNodeId);
              }}
              title={rowHintTitle ?? "Open related Map node"}
              type="button"
            />
          ) : hasLinkedIssue ? (
            <span aria-hidden="true" className="editor-row-link-mark" title="Linked to Map issue" />
          ) : null}
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

          const cellMinHeight = rowHeight ? Math.max(MIN_ROW_HEIGHT, rowHeight) : undefined;
          const isDuration = column.type === "duration";
          const commonProps = {
            value: isDuration ? durationInputValue(value) : value,
            onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
              const nextValue = event.target.value.replace(",", ".");
              if (isDuration && nextValue !== "" && !/^\d*(?:\.\d*)?$/.test(nextValue)) return;
              updateCell(row.row_id, column.column_id, nextValue);
            },
            placeholder: brandFeedback
              ? isShare
                ? "Enter your feedback for this scene"
                : "Filled by brand partner via share link"
              : isDuration
                ? "e.g. 5"
                : "",
            readOnly: cellReadOnly,
            onBlur: onCellBlur,
            onFocus: onCellFocus,
            title: brandFeedback
              ? isShare
                ? "Brand feedback — your comments are saved automatically"
                : "Brand feedback (read-only). Synced from the share page."
              : isShare
                ? "Read-only"
                : undefined
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
                  <div className="editor-duration-input-row">
                    <input
                      aria-label={`Scene ${rowMark} duration in seconds`}
                      className={`editor-table-input editor-duration-input ${hasDurationIssue ? "is-invalid" : ""}`}
                      inputMode="decimal"
                      {...commonProps}
                    />
                    <span className="editor-duration-unit">s</span>
                  </div>
                </div>
              ) : (
                <AutoSizeTextarea
                  className={`editor-table-cell cell-${column.key}${cellReadOnly ? " editor-table-cell--readonly" : ""}`}
                  minHeight={cellMinHeight}
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
            <button className="editor-row-insert-btn" onClick={onAddRow} title="Insert row" type="button">
              +
            </button>
          </td>
        </tr>
      ) : null}
    </>
  );
}

function formatClock(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const remainingSeconds = seconds - mins * 60;
  const secs = Number.isInteger(remainingSeconds)
    ? String(remainingSeconds).padStart(2, "0")
    : remainingSeconds.toFixed(2).replace(/0+$/, "").padStart(4, "0");
  return `${String(mins).padStart(2, "0")}:${secs}`;
}

function formatSeconds(seconds: number) {
  return Number.isInteger(seconds) ? String(seconds) : seconds.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
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
