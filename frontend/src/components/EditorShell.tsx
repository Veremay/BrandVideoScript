"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { CommunicationPanel } from "@/components/CommunicationPanel";
import { CoordinatorChat } from "@/components/CoordinatorChat";
import { RevisionProposalsProvider } from "@/components/RevisionProposalsPanel";
import { PersonaPanel } from "@/components/PersonaPanel";
import { RequirementsPanel } from "@/components/RequirementsPanel";
import { ScriptGrid } from "@/components/ScriptGrid";
import { ScriptSnapshotsPanel } from "@/components/ScriptSnapshotsPanel";
import { createShareLink, fetchProjectGraph, saveBrief, saveScript } from "@/lib/api";
import { useAppStore } from "@/store/appStore";

const MapView = dynamic(() => import("@/components/MapView").then((mod) => mod.MapView), {
  ssr: false,
  loading: () => <main className="centerStage">Loading Map…</main>
});

const SAVE_DELAY_MS = 700;
const FONT_SIZE_STORAGE_KEY = "brandvideo:font-size";
type FontSizePreference = "small" | "medium" | "large";

const FONT_SIZE_OPTIONS: Array<{ value: FontSizePreference; label: string }> = [
  { value: "small", label: "Small" },
  { value: "medium", label: "Medium" },
  { value: "large", label: "Large" }
];

async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall through to the legacy copy path when clipboard permission is denied.
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();

  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    textarea.remove();
  }
}

export function EditorShell() {
  const {
    appMode,
    editor,
    layout,
    project,
    script,
    setCoordinatorChatOpen,
    setProject,
    setSaveStatus,
    setSelection,
    setUserId,
    setPersonaPanelOpen,
    setRequirementsPanelOpen,
    setWorkspaceView
  } = useAppStore();
  const isVanilla = appMode === "vanilla";
  const hasHydrated = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [parsingBrief, setParsingBrief] = useState(false);
  const settingsRef = useRef<HTMLDivElement>(null);
  const activeView = isVanilla ? "editor" : layout.workspaceView;
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [snapshotsOpen, setSnapshotsOpen] = useState(false);
  const [communicationOpen, setCommunicationOpen] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [fontSize, setFontSize] = useState<FontSizePreference>("medium");
  const coordinatorOpen = layout.coordinatorChatOpen;
  const coordinatorDocked = layout.coordinatorChatDocked;

  useEffect(() => {
    const stored = window.localStorage.getItem(FONT_SIZE_STORAGE_KEY);
    if (stored === "small" || stored === "medium" || stored === "large") {
      setFontSize(stored);
    }
  }, []);

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

        // The request may finish after the user has typed again. In that case the
        // response contains an older script snapshot and must not replace the
        // newer controlled-input value in the store. The newer edit has already
        // scheduled its own save through this effect.
        if (useAppStore.getState().script !== script) return;

        setProject(savedProject);
        setSaveStatus("saved");
      } catch {
        // Do not mark a newer edit as failed because an older save request failed.
        if (useAppStore.getState().script !== script) return;
        setSaveStatus("failed");
      }
    }, SAVE_DELAY_MS);

    return () => window.clearTimeout(timeoutId);
  }, [editor.saveStatus, project, script, setProject, setSaveStatus]);

  useEffect(() => {
    if (activeView !== "map" || !project?._id || !project.user_id) return;
    let cancelled = false;
    fetchProjectGraph(project._id, project.user_id)
      .then((graph) => {
        if (cancelled) return;
        const current = useAppStore.getState().project;
        if (!current) return;
        setProject({
          ...current,
          rationale_nodes: graph.rationale_nodes,
          rationale_edges: graph.rationale_edges,
          updated_at: graph.updated_at
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [activeView, project?._id, project?.user_id, setProject]);

  useEffect(() => {
    if (!settingsOpen) return;

    function handlePointerDown(event: MouseEvent) {
      if (settingsRef.current?.contains(event.target as Node)) return;
      setSettingsOpen(false);
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [settingsOpen]);

  function handleBack() {
    window.localStorage.removeItem("brandvideo:project_id");
    setProject(null);
  }

  function handleLogout() {
    window.localStorage.removeItem("brandvideo:user_id");
    window.localStorage.removeItem("brandvideo:project_id");
    setUserId(undefined);
    setProject(null);
    setSettingsOpen(false);
  }

  function handleFabClick() {
    setCoordinatorChatOpen(!coordinatorOpen);
  }

  function handlePersonasClick() {
    setPersonaPanelOpen(true);
  }

  function handleRequirementsClick() {
    setRequirementsPanelOpen(true);
  }

  function openVersionHistory() {
    setSettingsOpen(false);
    setSnapshotsOpen(true);
  }

  function handleFontSizeChange(nextFontSize: FontSizePreference) {
    setFontSize(nextFontSize);
    window.localStorage.setItem(FONT_SIZE_STORAGE_KEY, nextFontSize);
  }

  async function persistBrief(text: string, filename?: string) {
    if (!project) return;
    setParsingBrief(true);
    try {
      // Upload only; requirements are parsed manually from the Requirements panel.
      const savedProject = await saveBrief(project._id, project.user_id, text, filename);
      setProject(savedProject);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Brief upload failed");
    } finally {
      setParsingBrief(false);
    }
  }

  async function handleBriefFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const isSupported = file.name.endsWith(".md") || file.name.endsWith(".txt");
    if (!isSupported) {
      window.alert("MVP supports .md and .txt briefs only.");
      return;
    }

    await persistBrief(await file.text(), file.name);
  }

  async function handleShare() {
    if (!project || sharing) return;
    setSharing(true);
    try {
      const { share_token } = await createShareLink(project._id, project.user_id);
      const shareUrl = `${window.location.origin}/share/${share_token}`;
      const copied = await copyTextToClipboard(shareUrl);
      window.alert(
        `${copied ? "Share link copied to clipboard." : "Share link created. Copy it below:"}\n\nBrand partners can open this link to fill in the Brand Feedback column only:\n${shareUrl}`
      );
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Failed to create share link");
    } finally {
      setSharing(false);
    }
  }

  if (!project || !script) return null;

  return (
    <RevisionProposalsProvider projectId={project._id} userId={project.user_id}>
      <main
        className={`app-figma${isVanilla && coordinatorOpen && coordinatorDocked ? " app-figma--chat-docked" : ""}`}
        data-font-size={fontSize}
      >
        <header className="figma-topnav">
          <div className="figma-topnav-left">
            <button className="figma-nav-btn figma-nav-back" onClick={handleBack} type="button">
              <IconBack />
              Back
            </button>
            {/* <span className="figma-brand-logo">BrandVideo</span> */}
            {!isVanilla && (
              <div className="figma-view-toggle" role="tablist" aria-label="Switch view">
                <button
                  className={`figma-view-tab ${activeView === "editor" ? "active" : ""}`}
                  onClick={() => setWorkspaceView("editor")}
                  type="button"
                  aria-selected={activeView === "editor"}
                >
                  <IconEditorList />
                  Editor
                </button>
                <button
                  className={`figma-view-tab ${activeView === "map" ? "active" : ""}`}
                  onClick={() => setWorkspaceView("map")}
                  type="button"
                  aria-selected={activeView === "map"}
                >
                  <IconMap />
                  Map
                </button>
              </div>
            )}
          </div>

          <div className="figma-topnav-right">
            {isVanilla ? null : (
              <>
                <input ref={fileInputRef} accept=".md,.txt,text/markdown,text/plain" hidden onChange={handleBriefFile} type="file" />
                <button
                  className="figma-nav-btn figma-nav-outline"
                  disabled={parsingBrief}
                  onClick={() => fileInputRef.current?.click()}
                  type="button"
                >
                  <IconUpload />
                  {parsingBrief ? "Uploading…" : "Upload Brief"}
                </button>
                {project.brief.filename ? <span className="figma-brief-tag">{project.brief.filename}</span> : null}
                {project.brief.parse_status ? (
                  <span className="figma-brief-tag figma-brief-tag--status">{project.brief.parse_status}</span>
                ) : null}
                <button className="figma-nav-btn figma-nav-outline" onClick={handleRequirementsClick} type="button">
                  <IconRequirements />
                  Requirements
                </button>
                <button className="figma-nav-btn figma-nav-outline" onClick={handlePersonasClick} type="button">
                  <IconPersonas />
                  Personas
                </button>
              </>
            )}
            <div className="figma-settings-wrap" ref={settingsRef}>
              <button
                aria-expanded={settingsOpen}
                aria-haspopup="menu"
                aria-label="Settings"
                className={`figma-icon-btn ${settingsOpen ? "active" : ""}`}
                onClick={() => setSettingsOpen((open) => !open)}
                type="button"
              >
                <IconSettings />
              </button>
              {settingsOpen ? (
                <div className="figma-settings-menu" role="menu">
                  <div className="figma-settings-menu-section">
                    <span className="figma-settings-menu-label">Script Setting</span>
                    <div className="figma-mode-static">
                      <span className="figma-mode-option-title">{isVanilla ? "Setting 2" : "Setting 1"}</span>
                      <span className="figma-mode-option-desc">Set when this script was created</span>
                    </div>
                  </div>
                  <div className="figma-settings-menu-divider" />
                  <div className="figma-settings-menu-section">
                    <span className="figma-settings-menu-label">Font Size</span>
                    <div className="figma-font-size-options" role="group" aria-label="Page font size">
                      {FONT_SIZE_OPTIONS.map((option) => (
                        <button
                          aria-pressed={fontSize === option.value}
                          className={`figma-font-size-option${fontSize === option.value ? " active" : ""}`}
                          key={option.value}
                          onClick={() => handleFontSizeChange(option.value)}
                          type="button"
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="figma-settings-menu-divider" />
                  <button className="figma-settings-menu-item" onClick={openVersionHistory} role="menuitem" type="button">
                    Version History
                  </button>
                  <button className="figma-settings-menu-item figma-settings-menu-item-danger" onClick={handleLogout} role="menuitem" type="button">
                    Sign Out
                  </button>
                </div>
              ) : null}
            </div>
            <button className="figma-nav-btn figma-nav-outline figma-nav-share" onClick={() => void handleShare()} disabled={sharing} type="button">
              {sharing ? "Sharing…" : "Share"}
            </button>
            <button className="figma-nav-btn figma-nav-primary" type="button">
              Export
            </button>
            <button className="figma-avatar-btn" onClick={handleLogout} title={project.title} type="button" aria-label="Account">
              <span className="figma-avatar-fallback">{project.title.slice(0, 1).toUpperCase()}</span>
            </button>
          </div>
        </header>

        <section className="figma-main">
          {activeView === "editor" ? (
            <div className="editor-workspace">
              <div className="editor-page-header">
                <h1 className="editor-page-title">Script Editor</h1>
              </div>
              <ScriptGrid script={script} />
            </div>
          ) : (
            <MapView key="map-workspace" />
          )}
        </section>

        {isVanilla ? (
          <>
            <button
              className={`figma-fab ${coordinatorOpen ? "figma-fab--open" : ""}`}
              onClick={handleFabClick}
              type="button"
              aria-label={coordinatorOpen ? "Close Coordinator Chat" : "Open Coordinator Chat"}
              aria-expanded={coordinatorOpen}
            >
              <IconRobot />
            </button>

            <CoordinatorChat
              open={coordinatorOpen}
              onClose={() => setCoordinatorChatOpen(false)}
              onClearQuote={() => setSelection(undefined)}
              selectedText={editor.selectedText}
              selectedRowId={editor.selectedRowId}
              selectedColumnId={editor.selectedColumnId}
              projectId={project._id}
              userId={project.user_id}
              scriptVersionId={project.current_script_version_id}
              userInitial={project.title.slice(0, 1).toUpperCase()}
              mode={appMode}
            />
          </>
        ) : (
          <>
            <RequirementsPanel onClose={() => setRequirementsPanelOpen(false)} open={layout.requirementsPanelOpen} />
            <PersonaPanel onClose={() => setPersonaPanelOpen(false)} open={layout.personaPanelOpen} />
            <button
              className={`figma-fab ${communicationOpen ? "figma-fab--open" : ""}`}
              onClick={() => setCommunicationOpen((value) => !value)}
              type="button"
              aria-label={communicationOpen ? "Close Communication panel" : "Open Communication panel"}
              aria-expanded={communicationOpen}
            >
              <IconHandshake />
            </button>
            <CommunicationPanel
              open={communicationOpen}
              onClose={() => setCommunicationOpen(false)}
              projectId={project._id}
              userId={project.user_id}
            />
          </>
        )}

        <ScriptSnapshotsPanel onClose={() => setSnapshotsOpen(false)} open={snapshotsOpen} />
      </main>
    </RevisionProposalsProvider>
  );
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

function IconRequirements() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
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

function IconSettings() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function IconRobot() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="5" y="9" width="14" height="11" rx="2" />
      <path d="M12 3v3" />
      <circle cx="12" cy="3" r="1" fill="currentColor" stroke="none" />
      <circle cx="9" cy="14" r="1" fill="currentColor" stroke="none" />
      <circle cx="15" cy="14" r="1" fill="currentColor" stroke="none" />
      <path d="M9 18h6" />
      <path d="M3 13v3" />
      <path d="M21 13v3" />
    </svg>
  );
}

function IconHandshake() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="m11 17 2 2a1 1 0 1 0 3-3" />
      <path d="m14 14 2.5 2.5a1 1 0 1 0 3-3l-3.88-3.88a3 3 0 0 0-4.24 0l-.88.88a1 1 0 1 1-3-3l2.81-2.81a5.79 5.79 0 0 1 7.06-.87l.47.28a2 2 0 0 0 1.42.25L21 4" />
      <path d="m21 3 1 11h-2" />
      <path d="M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3" />
      <path d="M3 4h8" />
    </svg>
  );
}
