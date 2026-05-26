"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { GlacierAssistant } from "@/components/GlacierAssistant";
import { PersonaPanel } from "@/components/PersonaPanel";
import { ScriptGrid } from "@/components/ScriptGrid";
import { saveBrief, saveScript } from "@/lib/api";
import { useAppStore } from "@/store/appStore";

const MapView = dynamic(() => import("@/components/MapView").then((mod) => mod.MapView), {
  ssr: false,
  loading: () => <main className="centerStage">Loading Map...</main>
});

const SAVE_DELAY_MS = 700;

export function EditorShell() {
  const {
    editor,
    layout,
    project,
    script,
    setBrandPinnedTab,
    setProject,
    setSaveStatus,
    setUserId,
    setActivePanel,
    setPersonaPanelOpen
  } = useAppStore();
  const hasHydrated = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
  const [activeView, setActiveView] = useState<"editor" | "map">("editor");

  useEffect(() => {
    if (layout.activePanel) {
      setAgentDrawerOpen(true);
    }
  }, [layout.activePanel]);

  useEffect(() => {
    if (!project || !script) return;

    if (!hasHydrated.current) {
      hasHydrated.current = true;
      return;
    }

    if (editor.saveStatus !== "editing") return;

    const timeoutId = window.setTimeout(async () => {
      setSaveStatus("saving");
      try {
        const savedProject = await saveScript(project._id, project.user_id, script);
        setProject(savedProject);
        setSaveStatus("saved");
      } catch {
        setSaveStatus("failed");
      }
    }, SAVE_DELAY_MS);

    return () => window.clearTimeout(timeoutId);
  }, [editor.saveStatus, project, script, setProject, setSaveStatus]);

  function handleBack() {
    setProject(null);
  }

  function handleLogout() {
    window.localStorage.removeItem("brandvideo:user_id");
    setUserId(undefined);
    setProject(null);
  }

  function handleFabClick() {
    if (agentDrawerOpen) {
      setAgentDrawerOpen(false);
      return;
    }
    setAgentDrawerOpen(true);
    if (!layout.activePanel) {
      setActivePanel("brand");
    }
  }

  function handlePersonasClick() {
    setPersonaPanelOpen(true);
  }

  async function persistBrief(text: string, filename?: string) {
    if (!project) return;
    const savedProject = await saveBrief(project._id, project.user_id, text, filename);
    setProject(savedProject);
    setBrandPinnedTab("explicit_requirement");
    setAgentDrawerOpen(true);
    setActivePanel("brand");
  }

  async function handleBriefFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const isSupported = file.name.endsWith(".md") || file.name.endsWith(".txt");
    if (!isSupported) {
      window.alert("当前 MVP 仅支持 .md / .txt Brief。");
      return;
    }

    await persistBrief(await file.text(), file.name);
  }

  if (!project || !script) return null;

  return (
    <main className="app-figma">
      <header className="figma-topnav">
        <div className="figma-topnav-left">
          <button className="figma-nav-btn figma-nav-back" onClick={handleBack} type="button">
            <IconBack />
            Back
          </button>
          <span className="figma-brand-logo">BrandVideo</span>
          <div className="figma-view-toggle" role="tablist" aria-label="Switch view">
            <button
              className={`figma-view-tab ${activeView === "editor" ? "active" : ""}`}
              onClick={() => setActiveView("editor")}
              type="button"
              aria-selected={activeView === "editor"}
            >
              <IconEditorList />
              Editor
            </button>
            <button
              className={`figma-view-tab ${activeView === "map" ? "active" : ""}`}
              onClick={() => setActiveView("map")}
              type="button"
              aria-selected={activeView === "map"}
            >
              <IconMap />
              Map
            </button>
          </div>
        </div>

        <div className="figma-topnav-right">
          <input ref={fileInputRef} accept=".md,.txt,text/markdown,text/plain" hidden onChange={handleBriefFile} type="file" />
          <button className="figma-nav-btn figma-nav-outline" onClick={() => fileInputRef.current?.click()} type="button">
            <IconUpload />
            Upload Brief
          </button>
          {project.brief.filename ? <span className="figma-brief-tag">{project.brief.filename}</span> : null}
          <button className="figma-nav-btn figma-nav-outline" onClick={handlePersonasClick} type="button">
            <IconPersonas />
            Personas
          </button>
          <button className="figma-icon-btn" type="button" aria-label="通知">
            <IconBell />
          </button>
          <button className="figma-icon-btn" onClick={handleLogout} title="退出登录" type="button" aria-label="设置">
            <IconSettings />
          </button>
          <button className="figma-nav-btn figma-nav-outline figma-nav-share" type="button">
            Share
          </button>
          <div className={`figma-save-pill status-${statusClass(editor.saveStatus)}`}>{statusLabel(editor.saveStatus)}</div>
          <button className="figma-nav-btn figma-nav-primary" type="button">
            Export
          </button>
          <button className="figma-avatar-btn" onClick={handleLogout} title={project.title} type="button" aria-label="用户">
            <span className="figma-avatar-fallback">{project.title.slice(0, 1).toUpperCase()}</span>
          </button>
        </div>
      </header>

      <section className="figma-main">
        {activeView === "editor" ? (
          <div className="editor-workspace">
            <div className="editor-page-header">
              <h1 className="editor-page-title">Script Editor</h1>
              <p className="editor-page-subtitle">{project.title}</p>
            </div>
            <ScriptGrid script={script} />
          </div>
        ) : (
          <MapView />
        )}
      </section>

      <button
        className={`figma-fab ${agentDrawerOpen ? "figma-fab--open" : ""}`}
        onClick={handleFabClick}
        type="button"
        aria-label={agentDrawerOpen ? "关闭 Glacier Assistant" : "打开 Glacier Assistant"}
        aria-expanded={agentDrawerOpen}
      >
        <IconLightning />
      </button>

      <GlacierAssistant
        open={agentDrawerOpen}
        onClose={() => setAgentDrawerOpen(false)}
        selectedText={editor.selectedText}
        userInitial={project.title.slice(0, 1).toUpperCase()}
      />

      <PersonaPanel onClose={() => setPersonaPanelOpen(false)} open={layout.personaPanelOpen} />
    </main>
  );
}

function statusClass(status: string) {
  if (status === "editing" || status === "saving") return "editing";
  if (status === "failed") return "failed";
  return "saved";
}

function statusLabel(status: string) {
  if (status === "editing") return "Editing";
  if (status === "saving") return "Saving";
  if (status === "failed") return "Failed";
  return "Saved";
}

function IconUpload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

function IconBack() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M19 12H5" />
      <path d="M12 19l-7-7 7-7" />
    </svg>
  );
}

function IconEditorList() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="8" x2="21" y1="6" y2="6" />
      <line x1="8" x2="21" y1="12" y2="12" />
      <line x1="8" x2="21" y1="18" y2="18" />
      <line x1="3" x2="3.01" y1="6" y2="6" />
      <line x1="3" x2="3.01" y1="12" y2="12" />
      <line x1="3" x2="3.01" y1="18" y2="18" />
    </svg>
  );
}

function IconMap() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <circle cx="5" cy="7" r="2" />
      <circle cx="19" cy="7" r="2" />
      <circle cx="7" cy="19" r="2" />
      <line x1="12" x2="5" y1="12" y2="7" />
      <line x1="12" x2="19" y1="12" y2="7" />
      <line x1="12" x2="7" y1="12" y2="19" />
    </svg>
  );
}

function IconPersonas() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function IconBell() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function IconLightning() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}
