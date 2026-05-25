"use client";

import { create } from "zustand";

import { insertColumn, insertRow, removeColumn, removeRow, renameColumn, updateCellValue } from "@/lib/scriptEditor";
import type { AgentType, BrandInsightCategory, Project, SaveStatus, Script } from "@/lib/types";

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
    activePanel: AgentType | null;
    agentsColWidth: number;
  };
  brand: {
    activePinnedTab: "explicit_requirement" | "implicit_requirement" | "brand_feedback";
    streaming: boolean;
  };
  audience: {
    activePersonaId?: string;
    modalMode: "create" | "edit" | null;
    streaming: boolean;
  };
  expert: {
    activeSuggestionId?: string;
    diffOverlayOpen: boolean;
    hunkState: Record<string, true | false | null>;
    streaming: boolean;
  };
  setUserId: (userId?: string) => void;
  setProjects: (projects: Project[]) => void;
  setProject: (project: Project | null) => void;
  setScript: (script: Script | null) => void;
  updateCell: (rowId: string, columnId: string, value: string) => void;
  setSaveStatus: (saveStatus: SaveStatus) => void;
  openPanel: (agent: AgentType | null) => void;
  setActivePanel: (agent: AgentType | null) => void;
  insertRowAfter: (rowId?: string) => void;
  deleteRow: (rowId: string) => void;
  insertColumnAfter: (columnId?: string, label?: string, multiline?: boolean) => void;
  deleteColumn: (columnId: string) => void;
  renameColumn: (columnId: string, label: string) => void;
  setAgentColumnWidth: (width: number) => void;
  setSelection: (selection?: { rowId?: string; columnId?: string; text: string }) => void;
  setBrandPinnedTab: (tab: BrandInsightCategory) => void;
};

export const useAppStore = create<AppState>((set) => ({
  projects: [],
  project: null,
  script: null,
  editor: {
    saveStatus: "saved"
  },
  layout: {
    activePanel: null,
    agentsColWidth: 360
  },
  brand: {
    activePinnedTab: "explicit_requirement",
    streaming: false
  },
  audience: {
    modalMode: null,
    streaming: false
  },
  expert: {
    diffOverlayOpen: false,
    hunkState: {},
    streaming: false
  },
  setUserId: (userId) => set({ userId }),
  setProjects: (projects) => set({ projects }),
  setProject: (project) =>
    set({
      project,
      script: project?.current_script ?? null,
      editor: { saveStatus: "saved" }
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
  openPanel: (agent) =>
    set((state) => ({
      layout: { ...state.layout, activePanel: state.layout.activePanel === agent ? null : agent }
    })),
  setActivePanel: (agent) =>
    set((state) => ({
      layout: { ...state.layout, activePanel: agent }
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
  insertColumnAfter: (columnId, label = "新列", multiline = false) =>
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
  setAgentColumnWidth: (width) =>
    set((state) => ({
      layout: { ...state.layout, agentsColWidth: Math.min(520, Math.max(280, width)) }
    })),
  setSelection: (selection) =>
    set((state) => ({
      editor: {
        ...state.editor,
        selectedRowId: selection?.rowId,
        selectedColumnId: selection?.columnId,
        selectedText: selection?.text
      }
    })),
  setBrandPinnedTab: (tab) =>
    set((state) => ({
      brand: { ...state.brand, activePinnedTab: tab }
    }))
}));
