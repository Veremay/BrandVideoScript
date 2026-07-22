"use client";

import { useLayoutEffect, useMemo, useRef, useState } from "react";

import { createEmptyInsight, insightsFromProject, toApiBrandInsights } from "@/lib/brandRequirements";
import {
  createPersona,
  parseBriefStream,
  provisionPersonasFromAnalytics,
  saveBrief,
  setActivePersona
} from "@/lib/api";
import { getPersonaEmoji } from "@/lib/personaEmoji";
import { getProjectSetupStatus } from "@/lib/projectSetup";
import type { BrandInsight, BrandInsightCategory, BrandInsightConfidence, PlatformContext } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

type ProjectSetupProps = {
  onBack: () => void;
  onEnterEditor: () => void;
};

export function ProjectSetup({ onBack, onEnterEditor }: ProjectSetupProps) {
  const { project, setProject } = useAppStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadingBrief, setUploadingBrief] = useState(false);
  const [parsingBrief, setParsingBrief] = useState(false);
  const [generatingPersonas, setGeneratingPersonas] = useState(false);
  const [creatingPersona, setCreatingPersona] = useState(false);
  const [activatingPersonaId, setActivatingPersonaId] = useState<string | null>(null);
  const [savingRequirements, setSavingRequirements] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Editable local copies — seed from project on first render, sync via handleParseBrief callback
  const [localExplicit, setLocalExplicit] = useState<BrandInsight[]>(() => {
    if (!project) return [];
    return insightsFromProject(project).explicit;
  });
  const [localImplicit, setLocalImplicit] = useState<BrandInsight[]>(() => {
    if (!project) return [];
    return insightsFromProject(project).implicit;
  });

  const isDirty = useMemo(() => {
    if (!project) return false;
    const current = insightsFromProject(project);
    return (
      JSON.stringify(current.explicit) !== JSON.stringify(localExplicit) ||
      JSON.stringify(current.implicit) !== JSON.stringify(localImplicit)
    );
  }, [localExplicit, localImplicit, project]);

  if (!project) return null;

  const status = getProjectSetupStatus(project);
  const hasBrief = Boolean(project.brief.text?.trim() || project.brief.filename);
  const hasRequirements = localExplicit.length > 0 || localImplicit.length > 0;
  const personaBusy = generatingPersonas || creatingPersona || activatingPersonaId !== null;
  const busy = uploadingBrief || parsingBrief || personaBusy;

  function updateLocalInsight(
    list: BrandInsight[],
    setList: (items: BrandInsight[]) => void,
    insightId: string,
    patch: Partial<BrandInsight>
  ) {
    setList(list.map((item) => (item.insight_id === insightId ? { ...item, ...patch } : item)));
  }

  function addLocalInsight(
    list: BrandInsight[],
    setList: (items: BrandInsight[]) => void,
    category: BrandInsightCategory
  ) {
    setList([...list, createEmptyInsight(category)]);
  }

  function removeLocalInsight(list: BrandInsight[], setList: (items: BrandInsight[]) => void, insightId: string) {
    setList(list.filter((item) => item.insight_id !== insightId));
  }

  async function handleSaveRequirements() {
    if (!project) return;
    const currentProject = project;
    setSavingRequirements(true);
    setError(null);

    const payload = toApiBrandInsights([...localExplicit, ...localImplicit]);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${currentProject._id}/brand/requirements`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: currentProject.user_id, brand_insights: payload }),
          signal: controller.signal,
        }
      );

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Save failed (${response.status})`);
      }

      const saved = await response.json();
      setProject(saved);
      const next = insightsFromProject(saved);
      setLocalExplicit(next.explicit);
      setLocalImplicit(next.implicit);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setError("Save timed out. Please try again.");
      } else {
        setError(err instanceof Error ? err.message : "Save failed");
      }
    } finally {
      clearTimeout(timeoutId);
      setSavingRequirements(false);
    }
  }

  async function persistBrief(text: string, filename?: string) {
    if (!project) return;
    setUploadingBrief(true);
    setError(null);
    try {
      const savedProject = await saveBrief(project._id, project.user_id, text, filename);
      setProject(savedProject);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Brief upload failed");
    } finally {
      setUploadingBrief(false);
    }
  }

  async function handleBriefFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const isSupported = file.name.endsWith(".md") || file.name.endsWith(".txt");
    if (!isSupported) {
      setError("MVP supports .md and .txt briefs only.");
      return;
    }

    await persistBrief(await file.text(), file.name);
  }

  async function handleParseBrief() {
    if (!project) return;
    setParsingBrief(true);
    setError(null);
    try {
      await parseBriefStream(project._id, project.user_id, (event) => {
        if (event.type === "done") {
          setProject(event.project);
          const fresh = insightsFromProject(event.project);
          setLocalExplicit(fresh.explicit);
          setLocalImplicit(fresh.implicit);
        } else if (event.type === "error") {
          setError(event.message);
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Brief parse failed");
    } finally {
      setParsingBrief(false);
    }
  }

  async function handleGeneratePersonas() {
    if (!project) return;
    setGeneratingPersonas(true);
    setError(null);
    try {
      const platform = (project.platform_context ?? "xiaohongshu") as PlatformContext;
      const result = await provisionPersonasFromAnalytics(project._id, project.user_id, {
        platform_context: platform,
        run_audience_parse: false
      });
      setProject(result.project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Persona generation failed");
    } finally {
      setGeneratingPersonas(false);
    }
  }

  async function handleAddPersona() {
    if (!project) return;
    setCreatingPersona(true);
    setError(null);
    try {
      const savedProject = await createPersona(project._id, project.user_id, {
        name: "New Audience Persona"
      });
      setProject(savedProject);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create persona");
    } finally {
      setCreatingPersona(false);
    }
  }

  async function handleActivatePersona(personaId: string) {
    if (!project || project.active_persona_id === personaId) return;
    setActivatingPersonaId(personaId);
    setError(null);
    try {
      const savedProject = await setActivePersona(project._id, project.user_id, personaId);
      setProject(savedProject);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set active persona");
    } finally {
      setActivatingPersonaId(null);
    }
  }

  return (
    <main className="app-hub setup-page">
      <div className="setup-shell">
        <header className="setup-header">
          <div className="setup-header-copy">
            <p className="hub-eyebrow">Project Setup</p>
            <h1 className="hub-headline">{project.title}</h1>
            <p className="hub-lead">
              Complete requirements parsing and persona provisioning before entering the editor.
            </p>
          </div>
          <button className="figma-nav-btn figma-nav-outline" disabled={busy} onClick={onBack} type="button">
            <IconBack />
            Back to Projects
          </button>
        </header>

        {error ? <p className="setup-alert setup-alert-error">{error}</p> : null}

        <section className="setup-progress" aria-label="Setup progress">
          <SetupStepBadge complete={status.requirementsComplete} label="Requirements" />
          <span className="setup-progress-line" />
          <SetupStepBadge complete={status.personaComplete} label="Persona" />
          <span className="setup-progress-line" />
          <SetupStepBadge complete={status.complete} label="Editor" />
        </section>

        <section className="setup-grid">
          <article className={`setup-card ${status.requirementsComplete ? "is-complete" : ""}`}>
            <div className="setup-card-header">
              <span className="setup-card-index">1</span>
              <div>
                <h2>Requirements Parsing</h2>
                <p>Upload a brief and the system will extract requirements. You can edit them later.</p>
              </div>
            </div>

            <div className="setup-card-scroll app-scrollbar">
              {hasRequirements ? (
                <div className="setup-item-groups">
                  <EditableRequirementGroup
                    items={localExplicit}
                    label="Explicit"
                    onAdd={() => addLocalInsight(localExplicit, setLocalExplicit, "explicit_requirement")}
                    onDelete={(id) => removeLocalInsight(localExplicit, setLocalExplicit, id)}
                    onUpdate={(id, patch) => updateLocalInsight(localExplicit, setLocalExplicit, id, patch)}
                  />
                  <EditableRequirementGroup
                    items={localImplicit}
                    label="Implicit"
                    onAdd={() => addLocalInsight(localImplicit, setLocalImplicit, "implicit_requirement")}
                    onDelete={(id) => removeLocalInsight(localImplicit, setLocalImplicit, id)}
                    onUpdate={(id, patch) => updateLocalInsight(localImplicit, setLocalImplicit, id, patch)}
                  />
                </div>
              ) : (
                <p className="setup-empty">No requirements parsed yet.</p>
              )}
            </div>

            <div className="setup-actions">
              <input
                ref={fileInputRef}
                accept=".md,.txt,text/markdown,text/plain"
                hidden
                onChange={handleBriefFile}
                type="file"
              />
              <button
                className="figma-nav-btn figma-nav-outline"
                disabled={busy}
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                <IconUpload />
                {uploadingBrief ? "Uploading..." : hasBrief ? "Replace Brief" : "Upload Brief"}
              </button>
              <button
                className="figma-nav-btn figma-nav-primary"
                disabled={busy || !hasBrief}
                onClick={() => void handleParseBrief()}
                type="button"
              >
                {parsingBrief ? "Parsing..." : status.requirementsComplete ? "Re-parse" : "Parse Requirements"}
              </button>
              {hasRequirements ? (
                <button
                  className="figma-nav-btn figma-nav-outline"
                  disabled={busy || savingRequirements || !isDirty}
                  onClick={() => void handleSaveRequirements()}
                  type="button"
                >
                  {savingRequirements ? "Saving…" : "Save Changes"}
                </button>
              ) : null}
            </div>
          </article>

          <article className={`setup-card ${status.personaComplete ? "is-complete" : ""}`}>
            <div className="setup-card-header">
              <span className="setup-card-index">2</span>
              <div>
                <h2>Persona Provisioning</h2>
                <p>Load defaults or add manually. Click a persona to set it active — at least one active persona is required.</p>
              </div>
            </div>

            <div className="setup-card-scroll app-scrollbar">
              {project.personas.length ? (
                <ul className="vanilla-setup-persona-list">
                  {project.personas.map((persona) => {
                    const isActive = project.active_persona_id === persona.persona_id;
                    return (
                      <li key={persona.persona_id}>
                        <button
                          className={`vanilla-setup-persona-item${isActive ? " is-active" : ""}`}
                          disabled={personaBusy}
                          onClick={() => void handleActivatePersona(persona.persona_id)}
                          type="button"
                        >
                          <span className="vanilla-setup-persona-avatar" aria-hidden="true">
                            {getPersonaEmoji(persona)}
                          </span>
                          <span className="vanilla-setup-persona-copy">
                            <strong>{persona.name}</strong>
                            <span>{persona.job || persona.explanation || "Audience persona"}</span>
                          </span>
                          {isActive ? <span className="vanilla-setup-persona-badge">Active</span> : null}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="setup-empty">No personas yet. Load from analytics or add one manually.</p>
              )}
            </div>

            <div className="setup-actions">
              <button
                className="figma-nav-btn figma-nav-outline"
                disabled={personaBusy || uploadingBrief || parsingBrief}
                onClick={() => void handleAddPersona()}
                type="button"
              >
                {creatingPersona ? "Adding…" : "Add New"}
              </button>
              <button
                className="figma-nav-btn figma-nav-primary"
                disabled={busy}
                onClick={() => void handleGeneratePersonas()}
                type="button"
              >
                {generatingPersonas
                  ? "Loading…"
                  : status.personaComplete
                    ? "Reload From Analytics"
                    : "From Analytics"}
              </button>
            </div>
          </article>
        </section>

        <footer className="setup-footer">
          <div>
            <strong>{status.complete ? "Setup complete" : "Setup required"}</strong>
            <p>
              {status.complete
                ? "You can enter the editor now. Requirements and personas remain editable from the toolbar."
                : "Both steps must be complete before the editor is available."}
            </p>
          </div>
          <button
            className="figma-nav-btn figma-nav-primary"
            disabled={!status.complete || busy}
            onClick={onEnterEditor}
            type="button"
          >
            Enter Editor
          </button>
        </footer>
      </div>
    </main>
  );
}

function AutoSizeTextarea({
  className,
  onChange,
  value,
  ...props
}: React.ComponentProps<"textarea">) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const syncHeight = () => {
    const node = ref.current;
    if (!node) return;
    node.style.height = "0px";
    node.style.height = `${node.scrollHeight}px`;
  };

  useLayoutEffect(() => {
    syncHeight();
  }, [value]);

  return (
    <textarea
      {...props}
      ref={ref}
      className={className}
      rows={1}
      value={value}
      onChange={(event) => {
        onChange?.(event);
        requestAnimationFrame(syncHeight);
      }}
    />
  );
}

function EditableRequirementGroup({
  items,
  label,
  onAdd,
  onDelete,
  onUpdate
}: {
  items: BrandInsight[];
  label: string;
  onAdd: () => void;
  onDelete: (insightId: string) => void;
  onUpdate: (insightId: string, patch: Partial<BrandInsight>) => void;
}) {
  if (!items.length) return null;

  return (
    <section className="setup-item-group">
      <h3 className="setup-item-group-title">
        {label} ({items.length})
      </h3>
      <ul className="setup-item-list">
        {items.map((item, index) => (
          <li className="setup-item setup-item--editable" key={item.insight_id}>
            <div className="setup-item-header">
              <span className="setup-item-index">#{index + 1}</span>
              <select
                className="setup-confidence-select"
                onChange={(e) => onUpdate(item.insight_id, { confidence: e.target.value as BrandInsightConfidence })}
                value={item.confidence}
              >
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <button
                aria-label="Delete requirement"
                className="setup-item-delete"
                onClick={() => onDelete(item.insight_id)}
                type="button"
              >
                <IconTrashSmall />
              </button>
            </div>
            <input
              className="setup-item-title-input"
              onChange={(e) => onUpdate(item.insight_id, { title: e.target.value })}
              placeholder="Title"
              type="text"
              value={item.title}
            />
            <AutoSizeTextarea
              className="setup-item-content-input"
              onChange={(e) => onUpdate(item.insight_id, { content: e.target.value })}
              placeholder="Describe this requirement…"
              value={item.content}
            />
            <AutoSizeTextarea
              className="setup-item-reason-input"
              onChange={(e) => onUpdate(item.insight_id, { reason: e.target.value })}
              placeholder="Reason (from Brief or inference)"
              value={item.reason}
            />
          </li>
        ))}
      </ul>
      <button className="setup-add-btn" onClick={onAdd} type="button">
        + Add {label.toLowerCase()} requirement
      </button>
    </section>
  );
}

function SetupStepBadge({ complete, label }: { complete: boolean; label: string }) {
  return (
    <span className={`setup-step-badge ${complete ? "is-complete" : ""}`}>
      {complete ? <IconCheck /> : <span className="setup-step-dot" />}
      {label}
    </span>
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

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function IconTrashSmall() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M2 4h12" />
      <path d="M12.667 4v9.333a1.333 1.333 0 0 1-1.334 1.334H4.667a1.333 1.333 0 0 1-1.334-1.334V4" />
      <path d="M5.333 4V2.667a1.333 1.333 0 0 1 1.334-1.334h2.666a1.333 1.333 0 0 1 1.334 1.334V4" />
    </svg>
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
