"use client";

import { useRef, useState } from "react";

import { insightsFromProject } from "@/lib/brandRequirements";
import { parseBriefStream, provisionPersonasFromAnalytics, saveBrief } from "@/lib/api";
import { getProjectSetupStatus } from "@/lib/projectSetup";
import type { BrandInsight, PlatformContext } from "@/lib/types";
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
  const [error, setError] = useState<string | null>(null);

  if (!project) return null;

  const status = getProjectSetupStatus(project);
  const { explicit: explicitRequirements, implicit: implicitRequirements } = insightsFromProject(project);
  const hasBrief = Boolean(project.brief.text?.trim() || project.brief.filename);
  const hasRequirements = explicitRequirements.length > 0 || implicitRequirements.length > 0;
  const busy = uploadingBrief || parsingBrief || generatingPersonas;

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
                  {explicitRequirements.length ? (
                    <section className="setup-item-group">
                      <h3 className="setup-item-group-title">Explicit ({explicitRequirements.length})</h3>
                      <ul className="setup-item-list">
                        {explicitRequirements.map((item, index) => (
                          <SetupRequirementItem index={index} item={item} key={item.insight_id} />
                        ))}
                      </ul>
                    </section>
                  ) : null}
                  {implicitRequirements.length ? (
                    <section className="setup-item-group">
                      <h3 className="setup-item-group-title">Implicit ({implicitRequirements.length})</h3>
                      <ul className="setup-item-list">
                        {implicitRequirements.map((item, index) => (
                          <SetupRequirementItem index={index} item={item} key={item.insight_id} />
                        ))}
                      </ul>
                    </section>
                  ) : null}
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
            </div>
          </article>

          <article className={`setup-card ${status.personaComplete ? "is-complete" : ""}`}>
            <div className="setup-card-header">
              <span className="setup-card-index">2</span>
              <div>
                <h2>Persona Provisioning</h2>
                <p>Generate at least one persona. You can edit them later.</p>
              </div>
            </div>

            <div className="setup-card-scroll app-scrollbar">
              {project.personas.length ? (
                <ul className="setup-persona-list">
                  {project.personas.map((persona) => (
                    <li key={persona.persona_id}>
                      <strong>{persona.name}</strong>
                      <span>{persona.job || persona.explanation || "Audience persona"}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="setup-empty">No personas generated yet.</p>
              )}
            </div>

            <div className="setup-actions">
              <button
                className="figma-nav-btn figma-nav-primary"
                disabled={busy}
                onClick={() => void handleGeneratePersonas()}
                type="button"
              >
                {generatingPersonas ? "Generating..." : status.personaComplete ? "Regenerate Personas" : "Generate Personas"}
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

function SetupRequirementItem({ item, index }: { item: BrandInsight; index: number }) {
  const label = item.title?.trim() || `Requirement #${index + 1}`;

  return (
    <li className="setup-item">
      <div className="setup-item-header">
        <strong>{label}</strong>
        <span className={`setup-item-confidence is-${item.confidence}`}>{item.confidence}</span>
      </div>
      <p>{item.content}</p>
      {item.reason?.trim() ? <p className="setup-item-reason">{item.reason}</p> : null}
    </li>
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

function IconUpload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}
