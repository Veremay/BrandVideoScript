"use client";

import { create } from "zustand";

import { mergeProjectPreservingGraph, normalizeProject } from "@/lib/normalizeProject";
import {
  abortMapSyncPipeline,
  abortSchemeGenPipeline,
  beginMapSyncAbortSignal,
  beginSchemeGenAbortSignal,
  clearMapSyncAbortController,
  clearSchemeGenAbortController
} from "@/lib/pipelineAbort";
import {
  clearPersistedSchemeGen,
  readPersistedSchemeGen,
  writePersistedSchemeGen
} from "@/lib/schemeGenPersistence";
import { insertColumn, insertRow, removeColumn, removeRow, renameColumn, updateCellValue, updateFeedbackCreatorReply } from "@/lib/scriptEditor";
import type { AppMode, PendingChatDraft, Project, SaveStatus, Script } from "@/lib/types";

type EditorState = {
  selectedRowId?: string;
  selectedColumnId?: string;
  selectedText?: string;
  saveStatus: SaveStatus;
};

export type MapSyncProgress = {
  step: number;
  total: number;
  message: string;
};

type MapSyncState = {
  projectId: string | null;
  syncing: boolean;
  progress: MapSyncProgress | null;
};

const EMPTY_MAP_SYNC: MapSyncState = {
  projectId: null,
  syncing: false,
  progress: null
};

export type SchemeGenProgress = {
  step: number;
  total: number;
  message: string;
};

type SchemeGenState = {
  projectId: string | null;
  generating: boolean;
  progress: SchemeGenProgress | null;
};

const EMPTY_SCHEME_GEN: SchemeGenState = {
  projectId: null,
  generating: false,
  progress: null
};

function resolveSchemeGenForProject(
  projectId: string | null | undefined,
  staleStatus: string | undefined,
  current: SchemeGenState
): SchemeGenState {
  if (!projectId) return EMPTY_SCHEME_GEN;
  if (current.generating && current.projectId === projectId) return current;

  const stored = readPersistedSchemeGen();
  if (staleStatus === "generating") {
    return {
      projectId,
      generating: true,
      progress: stored?.projectId === projectId ? stored.progress : null
    };
  }

  // Backend finished (or never started) — drop any leftover session progress.
  if (stored?.projectId === projectId) clearPersistedSchemeGen();
  return EMPTY_SCHEME_GEN;
}

function persistSchemeGen(state: SchemeGenState) {
  if (!state.generating || !state.projectId) {
    clearPersistedSchemeGen();
    return;
  }
  writePersistedSchemeGen({
    projectId: state.projectId,
    generating: true,
    progress: state.progress
  });
}

type AppState = {
  userId?: string;
  projects: Project[];
  project: Project | null;
  script: Script | null;
  appMode: AppMode;
  editor: EditorState;
  layout: {
    coordinatorChatOpen: boolean;
    coordinatorChatDocked: boolean;
    personaPanelOpen: boolean;
    requirementsPanelOpen: boolean;
    workspaceView: "editor" | "map";
  };
  mapFocusNodeId: string | null;
  editorSchemeFocusId: string | null;
  /** Survives MapView unmount when switching to Editor mid Update Map. */
  mapSync: MapSyncState;
  /** Survives Conflicts panel / MapView unmount mid Generate modification plan. */
  schemeGen: SchemeGenState;
  /** One-shot draft to inject into CoordinatorChat input (vanilla Argue). */
  pendingChatDraft: PendingChatDraft | null;
  undoStack: Script[];
  setUserId: (userId?: string) => void;
  setProjects: (projects: Project[]) => void;
  setProject: (project: Project | null) => void;
  setScript: (script: Script | null) => void;
  updateCell: (rowId: string, columnId: string, value: string) => void;
  updateFeedbackCreatorReply: (rowId: string, columnId: string, creatorReply: string) => void;
  setSaveStatus: (saveStatus: SaveStatus) => void;
  setCoordinatorChatOpen: (open: boolean) => void;
  setCoordinatorChatDocked: (docked: boolean) => void;
  setPendingChatDraft: (draft: PendingChatDraft | null) => void;
  insertRowAfter: (rowId?: string) => void;
  deleteRow: (rowId: string) => void;
  insertColumnAfter: (columnId?: string, label?: string, multiline?: boolean) => void;
  deleteColumn: (columnId: string) => void;
  renameColumn: (columnId: string, label: string, recordUndo?: boolean) => void;
  undoScript: () => void;
  setSelection: (selection?: { rowId?: string; columnId?: string; text: string }) => void;
  setPersonaPanelOpen: (open: boolean) => void;
  setRequirementsPanelOpen: (open: boolean) => void;
  setWorkspaceView: (view: "editor" | "map") => void;
  setMapFocusNodeId: (nodeId: string | null) => void;
  setEditorSchemeFocusId: (schemeId: string | null) => void;
  startMapSync: (projectId: string) => void;
  setMapSyncProgress: (progress: MapSyncProgress | null) => void;
  clearMapSync: () => void;
  abortMapSync: () => void;
  startSchemeGen: (projectId: string) => void;
  setSchemeGenProgress: (progress: SchemeGenProgress | null) => void;
  clearSchemeGen: () => void;
  abortSchemeGen: () => void;
};

const MAX_UNDO_STEPS = 100;

function appendUndoStep(stack: Script[], script: Script) {
  return [...stack, script].slice(-MAX_UNDO_STEPS);
}

export const useAppStore = create<AppState>((set) => ({
  projects: [],
  project: null,
  script: null,
  appMode: "full",
  editor: {
    saveStatus: "saved"
  },
  layout: {
    coordinatorChatOpen: false,
    coordinatorChatDocked: false,
    personaPanelOpen: false,
    requirementsPanelOpen: false,
    workspaceView: "editor"
  },
  mapFocusNodeId: null,
  editorSchemeFocusId: null,
  mapSync: EMPTY_MAP_SYNC,
  schemeGen: EMPTY_SCHEME_GEN,
  pendingChatDraft: null,
  undoStack: [],
  setUserId: (userId) => set({ userId }),
  setProjects: (projects) => set({ projects: projects.map((p) => normalizeProject(p)!).filter(Boolean) }),
  setProject: (project) =>
    set((state) => {
      const normalized = normalizeProject(project);
      const merged = normalized ? mergeProjectPreservingGraph(state.project, normalized) : null;
      const appMode = merged?.mode ?? merged?.current_script.settings?.mode ?? "full";
      const sameProject = state.project?._id === merged?._id;
      const schemeGen = resolveSchemeGenForProject(
        merged?._id,
        merged?.stale?.modification_schemes,
        sameProject ? state.schemeGen : EMPTY_SCHEME_GEN
      );
      if (!sameProject) clearPersistedSchemeGen();
      else persistSchemeGen(schemeGen);
      return {
        project: merged,
        script: merged?.current_script ?? null,
        appMode,
        editor: { saveStatus: "saved" },
        undoStack: sameProject ? state.undoStack : [],
        mapSync: sameProject ? state.mapSync : EMPTY_MAP_SYNC,
        schemeGen
      };
    }),
  setScript: (script) => set({ script }),
  updateCell: (rowId, columnId, value) =>
    set((state) => {
      if (!state.script) {
        return state;
      }
      const currentValue = state.script.rows
        .find((row) => row.row_id === rowId)
        ?.cells.find((cell) => cell.column_id === columnId)?.value;
      if (currentValue === value) return state;

      return {
        script: updateCellValue(state.script, rowId, columnId, value),
        editor: { ...state.editor, saveStatus: "editing" },
        undoStack: appendUndoStep(state.undoStack, state.script)
      };
    }),
  updateFeedbackCreatorReply: (rowId, columnId, creatorReply) =>
    set((state) => {
      if (!state.script) {
        return state;
      }
      const currentReply =
        state.script.rows
          .find((row) => row.row_id === rowId)
          ?.cells.find((cell) => cell.column_id === columnId)?.creator_reply ?? "";
      if (currentReply === creatorReply) return state;

      return {
        script: updateFeedbackCreatorReply(state.script, rowId, columnId, creatorReply)
      };
    }),
  setSaveStatus: (saveStatus) =>
    set((state) => ({
      editor: { ...state.editor, saveStatus }
    })),
  setCoordinatorChatOpen: (open) =>
    set((state) => ({
      layout: { ...state.layout, coordinatorChatOpen: open }
    })),
  setCoordinatorChatDocked: (docked) =>
    set((state) => ({
      layout: { ...state.layout, coordinatorChatDocked: docked }
    })),
  setPendingChatDraft: (draft) =>
    set((state) => {
      if (draft == null) return { pendingChatDraft: null };
      if (state.pendingChatDraft) {
        return {
          pendingChatDraft: {
            prompt: `${state.pendingChatDraft.prompt.trim()}\n\n${draft.appendBlock}`,
            appendBlock: draft.appendBlock
          }
        };
      }
      return { pendingChatDraft: draft };
    }),
  insertRowAfter: (rowId) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: insertRow(state.script, rowId),
        editor: { ...state.editor, saveStatus: "editing" },
        undoStack: appendUndoStep(state.undoStack, state.script)
      };
    }),
  deleteRow: (rowId) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: removeRow(state.script, rowId),
        editor: { ...state.editor, saveStatus: "editing" },
        undoStack: appendUndoStep(state.undoStack, state.script)
      };
    }),
  insertColumnAfter: (columnId, label = "New Column", multiline = false) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: insertColumn(state.script, columnId, label, multiline),
        editor: { ...state.editor, saveStatus: "editing" },
        undoStack: appendUndoStep(state.undoStack, state.script)
      };
    }),
  deleteColumn: (columnId) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: removeColumn(state.script, columnId),
        editor: { ...state.editor, saveStatus: "editing" },
        undoStack: appendUndoStep(state.undoStack, state.script)
      };
    }),
  renameColumn: (columnId, label, recordUndo = true) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: renameColumn(state.script, columnId, label),
        editor: { ...state.editor, saveStatus: "editing" },
        undoStack: recordUndo ? appendUndoStep(state.undoStack, state.script) : state.undoStack
      };
    }),
  undoScript: () =>
    set((state) => {
      const previousScript = state.undoStack.at(-1);
      if (!previousScript) return state;
      return {
        script: previousScript,
        undoStack: state.undoStack.slice(0, -1),
        editor: { ...state.editor, saveStatus: "editing" }
      };
    }),
  setSelection: (selection) =>
    set((state) => ({
      editor: {
        ...state.editor,
        selectedRowId: selection?.rowId,
        selectedColumnId: selection?.columnId,
        selectedText: selection?.text
      }
    })),
  setPersonaPanelOpen: (open) =>
    set((state) => ({
      layout: { ...state.layout, personaPanelOpen: open }
    })),
  setRequirementsPanelOpen: (open) =>
    set((state) => ({
      layout: { ...state.layout, requirementsPanelOpen: open }
    })),
  setWorkspaceView: (view) =>
    set((state) => ({
      layout: { ...state.layout, workspaceView: view }
    })),
  setMapFocusNodeId: (nodeId) => set({ mapFocusNodeId: nodeId }),
  setEditorSchemeFocusId: (schemeId) => set({ editorSchemeFocusId: schemeId }),
  startMapSync: (projectId) => {
    beginMapSyncAbortSignal();
    set({
      mapSync: { projectId, syncing: true, progress: null }
    });
  },
  setMapSyncProgress: (progress) =>
    set((state) => {
      if (!state.mapSync.syncing) return state;
      return { mapSync: { ...state.mapSync, progress } };
    }),
  clearMapSync: () => {
    clearMapSyncAbortController();
    set({ mapSync: EMPTY_MAP_SYNC });
  },
  abortMapSync: () => {
    abortMapSyncPipeline();
    set({ mapSync: EMPTY_MAP_SYNC });
  },
  startSchemeGen: (projectId) => {
    beginSchemeGenAbortSignal();
    const next: SchemeGenState = { projectId, generating: true, progress: null };
    persistSchemeGen(next);
    set({ schemeGen: next });
  },
  setSchemeGenProgress: (progress) =>
    set((state) => {
      if (!state.schemeGen.generating) return state;
      const next = { ...state.schemeGen, progress };
      persistSchemeGen(next);
      return { schemeGen: next };
    }),
  clearSchemeGen: () => {
    clearSchemeGenAbortController();
    clearPersistedSchemeGen();
    set({ schemeGen: EMPTY_SCHEME_GEN });
  },
  abortSchemeGen: () => {
    abortSchemeGenPipeline();
    clearPersistedSchemeGen();
    set({ schemeGen: EMPTY_SCHEME_GEN });
  }
}));
