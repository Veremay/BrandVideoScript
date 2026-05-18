"use client";

import { create } from "zustand";

import type { AgentType, Project, SaveStatus, Script } from "@/lib/types";

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

      const script: Script = {
        ...state.script,
        rows: state.script.rows.map((row) =>
          row.row_id === rowId
            ? {
                ...row,
                cells: row.cells.map((cell) =>
                  cell.column_id === columnId ? { ...cell, value } : cell
                )
              }
            : row
        )
      };

      return {
        script,
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
    }))
}));

