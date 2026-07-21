"use client";

import { useEffect, useRef, useState } from "react";

import { CoordinatorChat } from "@/components/CoordinatorChat";
import {
  createPersona,
  provisionPersonasFromAnalytics,
  setActivePersona,
  updateVanillaSetupStage
} from "@/lib/api";
import { getPersonaEmoji } from "@/lib/personaEmoji";
import type { PlatformContext, VanillaSetupData } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

type VanillaProjectSetupProps = {
  onBack: () => void;
  onEnterEditor: () => void;
};

const REQUIREMENTS_PROMPT =
  "Help me clarify the Brand Requirements panel. Ask focused questions, flag ambiguity, and suggest a concise version I can paste back into the panel.";
const CONFLICTS_PROMPT =
  "Help me identify conflicts and trade-offs in the brand requirements. Ask focused questions and suggest a concise analysis I can paste back into the Conflicts panel.";

export function VanillaProjectSetup({ onBack, onEnterEditor }: VanillaProjectSetupProps) {
  const { project, setPendingChatDraft, setProject } = useAppStore();
  const [formData, setFormData] = useState<VanillaSetupData>({
    brand_requirements: project?.vanilla_setup_data?.brand_requirements ?? "",
    conflicts: project?.vanilla_setup_data?.conflicts ?? ""
  });
  const formDataRef = useRef(formData);
  formDataRef.current = formData;
  const [assistantFocus, setAssistantFocus] = useState<"requirements" | "conflicts">("requirements");
  const [savingAction, setSavingAction] = useState<"enter" | null>(null);
  const [dirty, setDirty] = useState(false);
  const [autoSaveState, setAutoSaveState] = useState<"saved" | "pending" | "saving" | "failed">("saved");
  const [error, setError] = useState<string | null>(null);
  const [provisioningPersonas, setProvisioningPersonas] = useState(false);
  const [creatingPersona, setCreatingPersona] = useState(false);
  const [activatingPersonaId, setActivatingPersonaId] = useState<string | null>(null);

  useEffect(() => {
    if (!project || !dirty || savingAction) return;
    const timeoutId = window.setTimeout(async () => {
      const dataToSave = {
        brand_requirements: formData.brand_requirements.trim(),
        conflicts: formData.conflicts.trim()
      };
      setAutoSaveState("saving");
      try {
        const currentStage = project.vanilla_setup_stage === "conflicts" ? "conflicts" : "requirements";
        const savedProject = await updateVanillaSetupStage(
          project._id,
          project.user_id,
          currentStage,
          dataToSave
        );
        setProject(savedProject);
        const latestData = {
          brand_requirements: formDataRef.current.brand_requirements.trim(),
          conflicts: formDataRef.current.conflicts.trim()
        };
        const isLatest = JSON.stringify(latestData) === JSON.stringify(dataToSave);
        setDirty(!isLatest);
        setAutoSaveState(isLatest ? "saved" : "pending");
      } catch (err) {
        setAutoSaveState("failed");
        setError(err instanceof Error ? err.message : "Could not auto-save setup progress");
      }
    }, 700);
    return () => window.clearTimeout(timeoutId);
  }, [dirty, formData, project?._id, project?.user_id, project?.vanilla_setup_stage, savingAction, setProject]);

  if (!project) return null;

  const currentProject = project;
  const requirementsComplete = Boolean(formData.brand_requirements.trim());
  const conflictsComplete = Boolean(formData.conflicts.trim());
  const personaComplete = Boolean(
    project.personas.length > 0 &&
      project.active_persona_id &&
      project.personas.some((persona) => persona.persona_id === project.active_persona_id)
  );
  // Persona is optional — Enter Editor only requires requirements + conflicts.
  const setupComplete = requirementsComplete && conflictsComplete;
  const personaBusy = provisioningPersonas || creatingPersona || activatingPersonaId !== null;

  function updateField(field: keyof VanillaSetupData, value: string) {
    setFormData((current) => ({ ...current, [field]: value }));
    setDirty(true);
    setAutoSaveState("pending");
    setError(null);
  }

  function askAssistant(focus: "requirements" | "conflicts") {
    setAssistantFocus(focus);
    const value = focus === "requirements" ? formData.brand_requirements : formData.conflicts;
    const basePrompt = focus === "requirements" ? REQUIREMENTS_PROMPT : CONFLICTS_PROMPT;
    const prompt = value.trim() ? `${basePrompt}\n\nMy current notes:\n${value.trim()}` : basePrompt;
    setPendingChatDraft({ prompt, appendBlock: prompt });
  }

  function normalizedData(): VanillaSetupData {
    return {
      brand_requirements: formData.brand_requirements.trim(),
      conflicts: formData.conflicts.trim()
    };
  }

  async function handleProvisionPersonas() {
    setProvisioningPersonas(true);
    setError(null);
    try {
      const platform = (currentProject.platform_context ?? "xiaohongshu") as PlatformContext;
      const result = await provisionPersonasFromAnalytics(currentProject._id, currentProject.user_id, {
        platform_context: platform,
        run_audience_parse: false
      });
      setProject(result.project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Persona provisioning failed");
    } finally {
      setProvisioningPersonas(false);
    }
  }

  async function handleAddPersona() {
    setCreatingPersona(true);
    setError(null);
    try {
      const savedProject = await createPersona(currentProject._id, currentProject.user_id, {
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
    if (currentProject.active_persona_id === personaId) return;
    setActivatingPersonaId(personaId);
    setError(null);
    try {
      const savedProject = await setActivePersona(currentProject._id, currentProject.user_id, personaId);
      setProject(savedProject);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set active persona");
    } finally {
      setActivatingPersonaId(null);
    }
  }

  async function enterEditor() {
    if (!setupComplete) return;
    setSavingAction("enter");
    setDirty(false);
    setError(null);
    try {
      let savedProject = currentProject;
      if (savedProject.vanilla_setup_stage !== "conflicts") {
        savedProject = await updateVanillaSetupStage(
          savedProject._id,
          savedProject.user_id,
          "conflicts",
          normalizedData()
        );
      }
      savedProject = await updateVanillaSetupStage(
        savedProject._id,
        savedProject.user_id,
        "complete",
        normalizedData()
      );
      setProject(savedProject);
      setAutoSaveState("saved");
      onEnterEditor();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not complete project setup");
    } finally {
      setSavingAction(null);
    }
  }

  return (
    <main className="app-hub setup-page vanilla-setup-page">
      <div className="vanilla-setup-main">
        <header className="setup-header vanilla-setup-header">
          <div className="setup-header-copy">
            <p className="hub-eyebrow">Project Setup</p>
            <h1 className="hub-headline">{project.title}</h1>
            <p className="hub-lead">
              Complete requirements and conflicts to enter the editor. Persona is optional and used as chat context when set.
            </p>
          </div>
          <button className="figma-nav-btn figma-nav-outline" disabled={savingAction !== null} onClick={onBack} type="button">
            Back to Projects
          </button>
        </header>

        {error ? <p className="setup-alert setup-alert-error">{error}</p> : null}

        <section className="setup-progress" aria-label="Setup progress">
          <SetupBadge complete={requirementsComplete} label="Requirements" />
          <span className="setup-progress-line" />
          <SetupBadge complete={personaComplete} label="Persona" />
          <span className="setup-progress-line" />
          <SetupBadge complete={conflictsComplete} label="Conflicts" />
          <span className="setup-progress-line" />
          <SetupBadge complete={false} label="Editor" />
        </section>

        <section className="setup-grid vanilla-setup-grid">
          <SetupPanel
            complete={requirementsComplete}
            description="Write the brand goals, messages, rules, and constraints the script should follow."
            index="1"
            label="Brand Requirements"
            onAskAssistant={() => askAssistant("requirements")}
            onChange={(value) => updateField("brand_requirements", value)}
            placeholder="Brand goals, required messages, tone or visual rules, CTA, claims to avoid..."
            value={formData.brand_requirements}
          />

          <article className={`setup-card vanilla-setup-card${personaComplete ? " is-complete" : ""}`}>
            <div className="setup-card-header">
              <span className="setup-card-index">2</span>
              <div>
                <h2>Audience Persona</h2>
                <p>Optional. Load analytics defaults or add manually — used as chatbot context when active.</p>
              </div>
            </div>

            <div className="vanilla-setup-persona-body app-scrollbar">
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
                disabled={personaBusy}
                onClick={() => void handleAddPersona()}
                type="button"
              >
                {creatingPersona ? "Adding…" : "Add New"}
              </button>
              <button
                className="figma-nav-btn figma-nav-primary"
                disabled={personaBusy}
                onClick={() => void handleProvisionPersonas()}
                type="button"
              >
                {provisioningPersonas
                  ? "Loading…"
                  : personaComplete
                    ? "Reload From Analytics"
                    : "From Analytics"}
              </button>
            </div>
          </article>

          <SetupPanel
            complete={conflictsComplete}
            description="Write competing requirements, unresolved tensions, and what should take priority."
            index="3"
            label="Conflicts & Trade-offs"
            onAskAssistant={() => askAssistant("conflicts")}
            onChange={(value) => updateField("conflicts", value)}
            placeholder="Product detail vs. runtime, brand visibility vs. natural tone, priority decisions..."
            value={formData.conflicts}
          />
        </section>

        <footer className="setup-footer">
          <div>
            <strong>{setupComplete ? "Setup complete" : "Setup required"}</strong>
            <p>
              {setupComplete
                ? personaComplete
                  ? "Requirements and conflicts are ready. Active persona will be used in chat context."
                  : "Requirements and conflicts are ready. You can enter now — add a persona later if needed."
                : "Fill in both Requirements and Conflicts before entering the editor. Persona is optional."}
            </p>
          </div>
          <div className="vanilla-setup-footer-actions">
            <span className={`vanilla-auto-save-status is-${autoSaveState}`}>
              {autoSaveState === "saving"
                ? "Saving..."
                : autoSaveState === "pending"
                  ? "Changes pending"
                  : autoSaveState === "failed"
                    ? "Auto-save failed"
                    : "Saved automatically"}
            </span>
            <button
              className="figma-nav-btn figma-nav-primary"
              disabled={!setupComplete || savingAction !== null}
              onClick={() => void enterEditor()}
              type="button"
            >
              {savingAction === "enter" ? "Saving..." : "Enter Editor"}
            </button>
          </div>
        </footer>
      </div>

      <CoordinatorChat
        embedded
        messageTag={assistantFocus === "requirements" ? "REQUIREMENTS" : "CONFLICTS"}
        mode="vanilla"
        onClose={() => undefined}
        open
        projectId={project._id}
        scriptVersionId={project.current_script_version_id}
        userId={project.user_id}
        userInitial={project.title.slice(0, 1).toUpperCase()}
      />
    </main>
  );
}

type SetupPanelProps = {
  complete: boolean;
  description: string;
  index: string;
  label: string;
  onAskAssistant: () => void;
  onChange: (value: string) => void;
  placeholder: string;
  value: string;
};

function SetupPanel({ complete, description, index, label, onAskAssistant, onChange, placeholder, value }: SetupPanelProps) {
  const canAskAssistant = Boolean(value.trim());

  return (
    <article className={`setup-card vanilla-setup-card${complete ? " is-complete" : ""}`}>
      <div className="setup-card-header">
        <span className="setup-card-index">{index}</span>
        <div>
          <h2>{label}</h2>
          <p>{description}</p>
        </div>
      </div>
      <textarea
        aria-label={label}
        className="vanilla-setup-card-input"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        value={value}
      />
      <div className="setup-actions">
        <button
          className="figma-nav-btn figma-nav-outline"
          disabled={!canAskAssistant}
          onClick={onAskAssistant}
          type="button"
        >
          Ask AI to review
        </button>
      </div>
    </article>
  );
}

function SetupBadge({ complete, label }: { complete: boolean; label: string }) {
  return (
    <span className={`setup-step-badge${complete ? " is-complete" : ""}`}>
      {complete ? <IconCheck /> : <span className="setup-step-dot" />}
      {label}
    </span>
  );
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}
