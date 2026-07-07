"use client";

import { useEffect, useMemo, useState } from "react";

import { createPersona, deletePersona, provisionPersonasFromAnalytics, setActivePersona, updatePersona } from "@/lib/api";
import type { PlatformContext } from "@/lib/types";
import { getPersonaEmoji } from "@/lib/personaEmoji";
import type { Persona } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

type PersonaDraft = {
  name: string;
  job: string;
  explanation: string;
  characteristic_values: Record<string, string>;
  personal_experiences: string;
  reason: string;
};

type PersonaPanelProps = {
  open: boolean;
  onClose: () => void;
};

const EMPTY_DRAFT: PersonaDraft = {
  name: "",
  job: "",
  explanation: "",
  characteristic_values: {},
  personal_experiences: "",
  reason: ""
};

function experiencesToText(experiences: string[] | undefined): string {
  return (experiences ?? []).join("\n");
}

function textToExperiences(text: string): string[] {
  return text
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function personaToDraft(persona: Persona): PersonaDraft {
  return {
    name: persona.name ?? "",
    job: persona.job ?? "",
    explanation: persona.explanation ?? "",
    characteristic_values: { ...(persona.characteristic_values ?? {}) },
    personal_experiences: experiencesToText(persona.personal_experiences),
    reason: persona.reason ?? ""
  };
}

function personaSubtitle(persona: Persona): string {
  if (persona.job?.trim()) return persona.job.trim();
  if (persona.explanation?.trim()) return persona.explanation.trim();
  return "新观众画像";
}

export function PersonaPanel({ open, onClose }: PersonaPanelProps) {
  const { project, setProject } = useAppStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingActiveId, setPendingActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<PersonaDraft>(EMPTY_DRAFT);
  const [baselineDraft, setBaselineDraft] = useState<PersonaDraft>(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [provisioning, setProvisioning] = useState(false);

  const personas = project?.personas ?? [];
  const selectedPersona = useMemo(
    () => personas.find((persona) => persona.persona_id === selectedId) ?? null,
    [personas, selectedId]
  );

  useEffect(() => {
    if (!open || !project) return;

    const activeId = project.active_persona_id ?? project.personas[0]?.persona_id ?? null;
    setPendingActiveId(activeId);
    setSelectedId(activeId);

    const persona = project.personas.find((item) => item.persona_id === activeId);
    if (persona) {
      const nextDraft = personaToDraft(persona);
      setDraft(nextDraft);
      setBaselineDraft(nextDraft);
    } else {
      setDraft(EMPTY_DRAFT);
      setBaselineDraft(EMPTY_DRAFT);
    }
  }, [open, project?._id, project?.active_persona_id]);

  const currentProject = project!;
  const isDirty = JSON.stringify(draft) !== JSON.stringify(baselineDraft);

  if (!open || !project) return null;

  const characteristicEntries = Object.entries(draft.characteristic_values);

  function selectPersona(persona: Persona) {
    if (isDirty && !window.confirm("You have unsaved persona changes. Switch anyway?")) return;
    setSelectedId(persona.persona_id);
    const nextDraft = personaToDraft(persona);
    setDraft(nextDraft);
    setBaselineDraft(nextDraft);
  }

  function updateDraft<K extends keyof PersonaDraft>(key: K, value: PersonaDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function updateCharacteristicValue(key: string, value: string) {
    setDraft((current) => ({
      ...current,
      characteristic_values: { ...current.characteristic_values, [key]: value }
    }));
  }

  function resetDraft() {
    setDraft(baselineDraft);
  }

  async function handleSavePersona(): Promise<boolean> {
    if (!selectedPersona || !draft.name.trim()) {
      window.alert("请填写观众名称。");
      return false;
    }

    setSaving(true);
    try {
      const savedProject = await updatePersona(currentProject._id, currentProject.user_id, selectedPersona.persona_id, {
        name: draft.name.trim(),
        job: draft.job.trim(),
        explanation: draft.explanation.trim(),
        reason: draft.reason.trim(),
        personal_experiences: textToExperiences(draft.personal_experiences),
        characteristic_values: draft.characteristic_values
      });
      setProject(savedProject);
      const nextDraft = personaToDraft(
        savedProject.personas.find((persona) => persona.persona_id === selectedPersona.persona_id) ?? selectedPersona
      );
      setDraft(nextDraft);
      setBaselineDraft(nextDraft);
      return true;
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Save failed");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function handleProvisionFromAnalytics() {
    setProvisioning(true);
    try {
      const platform = (currentProject.platform_context ?? "xiaohongshu") as PlatformContext;
      const result = await provisionPersonasFromAnalytics(currentProject._id, currentProject.user_id, {
        platform_context: platform,
        run_audience_parse: true
      });
      if (result.project) {
        setProject(result.project);
        const activeId = result.active_persona_id ?? result.project.personas[0]?.persona_id ?? null;
        setPendingActiveId(activeId);
        setSelectedId(activeId);
        const persona = result.project.personas.find((item) => item.persona_id === activeId);
        if (persona) {
          const nextDraft = personaToDraft(persona);
          setDraft(nextDraft);
          setBaselineDraft(nextDraft);
        }
      }
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Persona provision failed");
    } finally {
      setProvisioning(false);
    }
  }

  async function handleAddPersona() {
    setCreating(true);
    try {
      const savedProject = await createPersona(currentProject._id, currentProject.user_id, {
        name: "新观众画像"
      });
      setProject(savedProject);
      const created = savedProject.personas[savedProject.personas.length - 1];
      if (created) {
        setSelectedId(created.persona_id);
        setPendingActiveId(created.persona_id);
        const nextDraft = personaToDraft(created);
        setDraft(nextDraft);
        setBaselineDraft(nextDraft);
      }
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  async function handleDeletePersona(personaId: string) {
    if (!window.confirm("Delete this persona?")) return;

    try {
      const savedProject = await deletePersona(currentProject._id, currentProject.user_id, personaId);
      setProject(savedProject);
      const nextActive = savedProject.active_persona_id ?? savedProject.personas[0]?.persona_id ?? null;
      setPendingActiveId(nextActive);
      setSelectedId(nextActive);
      const persona = savedProject.personas.find((item) => item.persona_id === nextActive);
      if (persona) {
        const nextDraft = personaToDraft(persona);
        setDraft(nextDraft);
        setBaselineDraft(nextDraft);
      } else {
        setDraft(EMPTY_DRAFT);
        setBaselineDraft(EMPTY_DRAFT);
      }
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Delete failed");
    }
  }

  async function handleApplyAll() {
    if (selectedPersona && isDirty) {
      const saved = await handleSavePersona();
      if (!saved) return;
    }

    try {
      const savedProject = await setActivePersona(currentProject._id, currentProject.user_id, pendingActiveId);
      setProject(savedProject);
      onClose();
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Apply failed");
    }
  }

  function handleClose() {
    if (isDirty && !window.confirm("You have unsaved changes. Close anyway?")) return;
    onClose();
  }

  return (
    <div className="persona-overlay" role="presentation">
      <button aria-label="Close persona panel" className="persona-overlay-backdrop" onClick={handleClose} type="button" />
      <section aria-labelledby="persona-panel-title" aria-modal="true" className="persona-panel" role="dialog">
        <button aria-label="Close" className="persona-panel-close" onClick={handleClose} type="button">
          <IconClose />
        </button>

        <header className="persona-panel-header">
          <div className="persona-panel-heading">
            <h1 className="persona-panel-title" id="persona-panel-title">
              Persona Management
            </h1>
            <p className="persona-panel-subtitle">
              定义并细化目标观众画像，优化 BrandVideo 的反馈闭环。点击 From Analytics 可载入默认分析结果。
            </p>
          </div>
          <div className="persona-panel-actions">
            <button
              className="persona-add-btn persona-add-btn-secondary"
              disabled={provisioning}
              onClick={handleProvisionFromAnalytics}
              type="button"
            >
              {provisioning ? "载入中…" : "From Analytics"}
            </button>
            <button className="persona-add-btn" disabled={creating} onClick={handleAddPersona} type="button">
              <IconPlus />
              Add New Persona
            </button>
          </div>
        </header>

        <div className="persona-panel-body">
          <aside className="persona-sidebar">
            <div className="persona-sidebar-label">Profile Directory</div>
            <div className="persona-card-list">
              {personas.length ? (
                personas.map((persona) => {
                  const isActive = pendingActiveId === persona.persona_id;
                  const isSelected = selectedId === persona.persona_id;
                  return (
                    <div
                      className={`persona-card ${isActive ? "active" : ""} ${isSelected ? "selected" : ""}`}
                      key={persona.persona_id}
                    >
                      <button
                        className="persona-card-main"
                        onClick={() => {
                          selectPersona(persona);
                          setPendingActiveId(persona.persona_id);
                        }}
                        type="button"
                      >
                        <span className="persona-card-avatar">{getPersonaEmoji(persona)}</span>
                        <span className="persona-card-copy">
                          <span className="persona-card-name">{persona.name}</span>
                          <span className="persona-card-meta">{personaSubtitle(persona)}</span>
                        </span>
                      </button>
                      <button
                        aria-label={`Delete ${persona.name}`}
                        className="persona-card-delete"
                        onClick={() => handleDeletePersona(persona.persona_id)}
                        type="button"
                      >
                        <IconTrash />
                      </button>
                    </div>
                  );
                })
              ) : (
                <div className="persona-empty">暂无观众画像。点击 Add New Persona 创建，或 From Analytics 载入默认数据。</div>
              )}
            </div>
          </aside>

          <div className="persona-editor">
            <div className="persona-editor-header">
              <IconEdit />
              <h2>Profile Configuration</h2>
            </div>

            {selectedPersona ? (
              <>
                <div className="persona-form-grid">
                  <label className="persona-field">
                    <span>名称（Name）</span>
                    <input onChange={(event) => updateDraft("name", event.target.value)} value={draft.name} />
                  </label>

                  <label className="persona-field">
                    <span>职业（Job）</span>
                    <input onChange={(event) => updateDraft("job", event.target.value)} value={draft.job} />
                  </label>

                  <label className="persona-field persona-field-full">
                    <span>人物简介（Explanation）</span>
                    <textarea
                      onChange={(event) => updateDraft("explanation", event.target.value)}
                      rows={3}
                      value={draft.explanation}
                    />
                  </label>

                  <div className="persona-field persona-field-full">
                    <span>特征（Characteristic Values）</span>
                    <div className="persona-kv-list">
                      {characteristicEntries.length ? (
                        characteristicEntries.map(([key, value]) => (
                          <div className="persona-kv-row" key={key}>
                            <span className="persona-kv-key">{key}</span>
                            <span aria-hidden="true" className="persona-kv-sep">
                            
                            </span>
                            <input
                              className="persona-kv-value"
                              onChange={(event) => updateCharacteristicValue(key, event.target.value)}
                              value={value}
                            />
                          </div>
                        ))
                      ) : (
                        <div className="persona-kv-empty">暂无特征数据</div>
                      )}
                    </div>
                  </div>

                  <label className="persona-field persona-field-full">
                    <span>可能的经历（Personal Experiences）</span>
                    <textarea
                      onChange={(event) => updateDraft("personal_experiences", event.target.value)}
                      placeholder="每行一条经历"
                      rows={5}
                      value={draft.personal_experiences}
                    />
                  </label>

                  <label className="persona-field persona-field-full">
                    <span>观看动机（Reason）</span>
                    <textarea onChange={(event) => updateDraft("reason", event.target.value)} rows={3} value={draft.reason} />
                  </label>
                </div>

                <div className="persona-editor-actions">
                  <button className="persona-reset-btn" disabled={!isDirty || saving} onClick={resetDraft} type="button">
                    Reset Changes
                  </button>
                  <button className="persona-save-btn" disabled={saving} onClick={handleSavePersona} type="button">
                    {saving ? "Saving..." : "Save Persona"}
                  </button>
                </div>
              </>
            ) : (
              <div className="persona-editor-empty">选择或创建一个观众画像进行配置。</div>
            )}
          </div>
        </div>

        <footer className="persona-panel-footer">
          <button className="persona-cancel-btn" onClick={handleClose} type="button">
            Cancel
          </button>
          <button className="persona-apply-btn" disabled={!personas.length} onClick={handleApplyAll} type="button">
            Apply All Settings
          </button>
        </footer>
      </section>
    </div>
  );
}

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="18" x2="6" y1="6" y2="18" />
      <line x1="6" x2="18" y1="6" y2="18" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="12" x2="12" y1="5" y2="19" />
      <line x1="5" x2="19" y1="12" y2="12" />
    </svg>
  );
}

function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14H6L5 6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M9 6V4h6v2" />
    </svg>
  );
}

function IconEdit() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}
