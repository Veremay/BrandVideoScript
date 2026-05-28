"use client";

import { create } from "zustand";

import { mergeProjectPreservingGraph, normalizeProject } from "@/lib/normalizeProject";
import { insertColumn, insertRow, removeColumn, removeRow, renameColumn, updateCellValue } from "@/lib/scriptEditor";
import type { Project, SaveStatus, Script } from "@/lib/types";

type EditorState = {
  selectedRowId?: string;
  selectedColumnId?: string;
  selectedText?: string;
  saveStatus: SaveStatus;
};

type AppState = {
  userId?: string;
  projects: Project[];
  project: Project | null;
  script: Script | null;
  editor: EditorState;
  layout: {
    coordinatorChatOpen: boolean;
    personaPanelOpen: boolean;
    requirementsPanelOpen: boolean;
    workspaceView: "editor" | "map";
  };
  editorSchemeFocusId: string | null;
  setUserId: (userId?: string) => void;
  setProjects: (projects: Project[]) => void;
  setProject: (project: Project | null) => void;
  setScript: (script: Script | null) => void;
  updateCell: (rowId: string, columnId: string, value: string) => void;
  setSaveStatus: (saveStatus: SaveStatus) => void;
  setCoordinatorChatOpen: (open: boolean) => void;
  openCoordinatorWithQuote: (selection: { rowId: string; columnId: string; text: string }) => void;
  insertRowAfter: (rowId?: string) => void;
  deleteRow: (rowId: string) => void;
  insertColumnAfter: (columnId?: string, label?: string, multiline?: boolean) => void;
  deleteColumn: (columnId: string) => void;
  renameColumn: (columnId: string, label: string) => void;
  setSelection: (selection?: { rowId?: string; columnId?: string; text: string }) => void;
  setPersonaPanelOpen: (open: boolean) => void;
  setRequirementsPanelOpen: (open: boolean) => void;
  setWorkspaceView: (view: "editor" | "map") => void;
  setEditorSchemeFocusId: (schemeId: string | null) => void;
};

export const useAppStore = create<AppState>((set) => ({
  projects: [],
  project: null,
  script: null,
  editor: {
    saveStatus: "saved"
  },
  layout: {
    coordinatorChatOpen: false,
    personaPanelOpen: false,
    requirementsPanelOpen: false,
    workspaceView: "editor"
  },
  editorSchemeFocusId: null,
  setUserId: (userId) => set({ userId }),
  setProjects: (projects) => set({ projects: projects.map((p) => normalizeProject(p)!).filter(Boolean) }),
  setProject: (project) =>
    set((state) => {
      const normalized = normalizeProject(project);
      const merged = normalized ? mergeProjectPreservingGraph(state.project, normalized) : null;
      return {
        project: merged,
        script: merged?.current_script ?? null,
        editor: { saveStatus: "saved" }
      };
    }),
  setScript: (script) => set({ script }),
  updateCell: (rowId, columnId, value) =>
    set((state) => {
      if (!state.script) {
        return state;
      }

      return {
        script: updateCellValue(state.script, rowId, columnId, value),
        editor: { ...state.editor, saveStatus: "editing" }
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
  openCoordinatorWithQuote: (selection) =>
    set((state) => ({
      editor: {
        ...state.editor,
        selectedRowId: selection.rowId,
        selectedColumnId: selection.columnId,
        selectedText: selection.text
      },
      layout: { ...state.layout, coordinatorChatOpen: true }
    })),
  insertRowAfter: (rowId) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: insertRow(state.script, rowId),
        editor: { ...state.editor, saveStatus: "editing" }
      };
    }),
  deleteRow: (rowId) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: removeRow(state.script, rowId),
        editor: { ...state.editor, saveStatus: "editing" }
      };
    }),
  insertColumnAfter: (columnId, label = "New Column", multiline = false) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: insertColumn(state.script, columnId, label, multiline),
        editor: { ...state.editor, saveStatus: "editing" }
      };
    }),
  deleteColumn: (columnId) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: removeColumn(state.script, columnId),
        editor: { ...state.editor, saveStatus: "editing" }
      };
    }),
  renameColumn: (columnId, label) =>
    set((state) => {
      if (!state.script) return state;
      return {
        script: renameColumn(state.script, columnId, label),
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
  setEditorSchemeFocusId: (schemeId) => set({ editorSchemeFocusId: schemeId })
}));
