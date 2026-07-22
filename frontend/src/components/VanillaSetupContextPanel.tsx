"use client";

import { useEffect, useRef, useState } from "react";

import { fetchProject, generateModificationSchemesStream, updateVanillaSetupStage } from "@/lib/api";
import type { VanillaSetupData } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

type VanillaSetupSection = "requirements" | "conflicts";

type VanillaSetupContextPanelProps = {
  onClose: () => void;
  open: boolean;
  section: VanillaSetupSection;
};

function hasScriptContent(project: { current_script?: { rows?: Array<{ cells?: Array<{ value?: string }> }> } } | null) {
  return (project?.current_script?.rows ?? []).some((row) =>
    (row.cells ?? []).some((cell) => String(cell.value ?? "").trim().length > 0)
  );
}

export function VanillaSetupContextPanel({ onClose, open, section }: VanillaSetupContextPanelProps) {
  const project = useAppStore((state) => state.project);
  const setProject = useAppStore((state) => state.setProject);
  const setEditorSchemeFocusId = useAppStore((state) => state.setEditorSchemeFocusId);
  const schemeGen = useAppStore((state) => state.schemeGen);
  const startSchemeGen = useAppStore((state) => state.startSchemeGen);
  const setSchemeGenProgress = useAppStore((state) => state.setSchemeGenProgress);
  const clearSchemeGen = useAppStore((state) => state.clearSchemeGen);
  const isRequirements = section === "requirements";
  const title = isRequirements ? "Brand Requirements" : "Conflicts & Trade-offs";
  const fieldKey: keyof VanillaSetupData = isRequirements ? "brand_requirements" : "conflicts";
  const storedValue = project?.vanilla_setup_data?.[fieldKey] ?? "";

  const generating =
    (schemeGen.generating && schemeGen.projectId === project?._id) ||
    project?.stale?.modification_schemes === "generating";
  const generateProgress = schemeGen.projectId === project?._id ? schemeGen.progress : null;

  const [draft, setDraft] = useState(storedValue);
  const draftRef = useRef(draft);
  draftRef.current = draft;
  const [dirty, setDirty] = useState(false);
  const [saveState, setSaveState] = useState<"saved" | "pending" | "saving" | "failed">("saved");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDraft(storedValue);
    draftRef.current = storedValue;
    setDirty(false);
    setSaveState("saved");
    setError(null);
  }, [open, section, storedValue, project?._id]);

  useEffect(() => {
    if (!open || !project || !dirty || generating) return;
    const timeoutId = window.setTimeout(async () => {
      const nextValue = draftRef.current;
      const data: VanillaSetupData = {
        brand_requirements:
          fieldKey === "brand_requirements"
            ? nextValue.trim()
            : project.vanilla_setup_data?.brand_requirements?.trim() ?? "",
        conflicts:
          fieldKey === "conflicts" ? nextValue.trim() : project.vanilla_setup_data?.conflicts?.trim() ?? ""
      };
      setSaveState("saving");
      try {
        const stage =
          project.vanilla_setup_stage === "requirements" || project.vanilla_setup_stage === "conflicts"
            ? project.vanilla_setup_stage
            : "complete";
        const saved = await updateVanillaSetupStage(project._id, project.user_id, stage, data);
        setProject(saved);
        const latest = draftRef.current;
        const savedField = fieldKey === "brand_requirements" ? data.brand_requirements : data.conflicts;
        const isLatest = latest.trim() === savedField;
        setDirty(!isLatest);
        setSaveState(isLatest ? "saved" : "pending");
      } catch (err) {
        setSaveState("failed");
        setError(err instanceof Error ? err.message : "Could not save");
      }
    }, 700);
    return () => window.clearTimeout(timeoutId);
  }, [dirty, draft, fieldKey, generating, open, project, setProject]);

  if (!open || !project) return null;

  const placeholder = isRequirements
    ? "Brand goals, required messages, tone or visual rules, CTA, claims to avoid..."
    : "Product detail vs. runtime, brand visibility vs. natural tone, priority decisions...";
  const subtitle = isRequirements
    ? "Used as context by the AI assistant. Changes save automatically."
    : "Capture competing requirements and trade-offs. Generate a modification plan for the script from this context.";

  const requirementsText = isRequirements
    ? draft.trim()
    : project.vanilla_setup_data?.brand_requirements?.trim() ?? "";
  const conflictsText = isRequirements ? project.vanilla_setup_data?.conflicts?.trim() ?? "" : draft.trim();
  const canGeneratePlan =
    !isRequirements &&
    !generating &&
    Boolean(conflictsText || requirementsText) &&
    hasScriptContent(project);

  async function flushDraft(): Promise<typeof project> {
    if (!project) return null;
    if (!dirty) return project;
    const nextValue = draftRef.current;
    const data: VanillaSetupData = {
      brand_requirements:
        fieldKey === "brand_requirements"
          ? nextValue.trim()
          : project.vanilla_setup_data?.brand_requirements?.trim() ?? "",
      conflicts:
        fieldKey === "conflicts" ? nextValue.trim() : project.vanilla_setup_data?.conflicts?.trim() ?? ""
    };
    setSaveState("saving");
    const stage =
      project.vanilla_setup_stage === "requirements" || project.vanilla_setup_stage === "conflicts"
        ? project.vanilla_setup_stage
        : "complete";
    const saved = await updateVanillaSetupStage(project._id, project.user_id, stage, data);
    setProject(saved);
    setDirty(false);
    setSaveState("saved");
    return saved;
  }

  async function handleGenerateModificationPlan() {
    if (!project || generating || isRequirements) return;
    if (!hasScriptContent(project)) {
      setError("Add script content in the editor before generating a modification plan.");
      return;
    }
    if (!conflictsText && !requirementsText) {
      setError("Add conflicts or brand requirements before generating a plan.");
      return;
    }

    const projectId = project._id;
    const userId = project.user_id;
    startSchemeGen(projectId);
    setError(null);
    try {
      await flushDraft();
      await generateModificationSchemesStream(
        projectId,
        userId,
        {
          target_position_ids: [],
          target_issue_ids: [],
          message:
            "Generate one script modification plan from the creator's Brand Requirements, Conflicts & Trade-offs, and active Persona. Prefer concrete cell-level hunks."
        },
        (event) => {
          if (event.type === "progress") {
            setSchemeGenProgress({ step: event.step, total: event.total, message: event.message });
          }
          if (event.type === "done") {
            if (!event.project) return;
            const prev = useAppStore.getState().schemeGen.progress;
            setSchemeGenProgress({
              step: prev?.total ?? 1,
              total: prev?.total ?? 1,
              message: "Complete"
            });
            window.setTimeout(() => {
              setProject(event.project!);
              const latest = event.schemes[event.schemes.length - 1];
              if (latest?.scheme_id) {
                setEditorSchemeFocusId(latest.scheme_id);
              }
              clearSchemeGen();
              onClose();
            }, 350);
          }
          if (event.type === "error") {
            throw new Error(event.message);
          }
        }
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate modification plan";
      setError(message);
      clearSchemeGen();
      try {
        const refreshed = await fetchProject(projectId, userId);
        setProject(refreshed);
      } catch {
        // ignore refresh failure
      }
    }
  }

  const progressPercent =
    generateProgress && generateProgress.total > 0
      ? Math.min(100, Math.round((generateProgress.step / generateProgress.total) * 100))
      : generating
        ? 8
        : 0;

  return (
    <div className="persona-overlay" role="presentation">
      <button aria-label={`Close ${title}`} className="persona-overlay-backdrop" onClick={onClose} type="button" />
      <section
        aria-labelledby="vanilla-context-title"
        aria-modal="true"
        className="persona-panel vanilla-context-panel"
        role="dialog"
      >
        <button aria-label="Close" className="persona-panel-close" onClick={onClose} type="button">
          <IconClose />
        </button>
        <header className="persona-panel-header">
          <div className="persona-panel-heading">
            <h1 className="persona-panel-title" id="vanilla-context-title">{title}</h1>
            <p className="persona-panel-subtitle">{subtitle}</p>
          </div>
        </header>
        <div className="vanilla-context-body app-scrollbar">
          <textarea
            aria-label={title}
            className="vanilla-context-editor"
            disabled={generating}
            onChange={(event) => {
              setDraft(event.target.value);
              setDirty(true);
              setSaveState("pending");
              setError(null);
            }}
            placeholder={placeholder}
            rows={14}
            value={draft}
          />
          <div className="vanilla-context-footer">
            <span className={`vanilla-auto-save-status is-${saveState}`}>
              {saveState === "saving"
                ? "Saving..."
                : saveState === "pending"
                  ? "Changes pending"
                  : saveState === "failed"
                    ? "Save failed"
                    : "Saved automatically"}
            </span>
            {error ? <p className="setup-alert setup-alert-error">{error}</p> : null}
            {!isRequirements ? (
              <button
                className="vanilla-generate-plan-btn"
                disabled={!canGeneratePlan}
                onClick={() => void handleGenerateModificationPlan()}
                title={
                  !hasScriptContent(project)
                    ? "Add script content first"
                    : !conflictsText && !requirementsText
                      ? "Add conflicts or requirements first"
                      : (generateProgress?.message ?? undefined)
                }
                type="button"
              >
                {generating ? (
                  <span className="btn-progress-fill" style={{ transform: `scaleX(${progressPercent / 100})` }} />
                ) : null}
                <span className="btn-progress-label">
                  {generating
                    ? `Generating… ${progressPercent}%`
                    : "Generate modification plan"}
                </span>
              </button>
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}
