"use client";

import { useEffect, useMemo, useState } from "react";

import { createPersona, deletePersona, setActivePersona, updatePersona } from "@/lib/api";
import { getPersonaEmoji, randomPersonaEmoji } from "@/lib/personaEmoji";
import type { Persona, PersonaAdSensitivity } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

type PersonaDraft = {
  name: string;
  gender: string;
  age_range: string;
  preferences: string;
  platform_context: string;
  ad_sensitivity: PersonaAdSensitivity;
  behavior: string;
  trust_trigger: string;
  reject_trigger: string;
};

type PersonaPanelProps = {
  open: boolean;
  onClose: () => void;
};

const EMPTY_DRAFT: PersonaDraft = {
  name: "",
  gender: "",
  age_range: "",
  preferences: "",
  platform_context: "",
  ad_sensitivity: "medium",
  behavior: "",
  trust_trigger: "",
  reject_trigger: ""
};

function personaToDraft(persona: Persona): PersonaDraft {
  return {
    name: persona.name,
    gender: persona.gender,
    age_range: persona.age_range,
    preferences: persona.preferences,
    platform_context: persona.platform_context,
    ad_sensitivity: persona.ad_sensitivity,
    behavior: persona.behavior,
    trust_trigger: persona.trust_trigger.join(", "),
    reject_trigger: persona.reject_trigger.join(", ")
  };
}

function listFromText(value: string): string[] {
  return value
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function personaSubtitle(persona: Persona): string {
  const parts = [persona.preferences, persona.age_range].map((item) => item.trim()).filter(Boolean);
  if (parts.length) return parts.join(", ");
  if (persona.gender.trim()) return persona.gender;
  return "New profile";
}

export function PersonaPanel({ open, onClose }: PersonaPanelProps) {
  const { project, setProject } = useAppStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingActiveId, setPendingActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<PersonaDraft>(EMPTY_DRAFT);
  const [baselineDraft, setBaselineDraft] = useState<PersonaDraft>(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);

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

  if (!open || !project) return null;

  const currentProject = project;
  const isDirty = JSON.stringify(draft) !== JSON.stringify(baselineDraft);

  function selectPersona(persona: Persona) {
    if (isDirty && !window.confirm("当前 persona 有未保存修改，确定切换吗？")) return;
    setSelectedId(persona.persona_id);
    const nextDraft = personaToDraft(persona);
    setDraft(nextDraft);
    setBaselineDraft(nextDraft);
  }

  function updateDraft<K extends keyof PersonaDraft>(key: K, value: PersonaDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function resetDraft() {
    setDraft(baselineDraft);
  }

  async function handleSavePersona(): Promise<boolean> {
    if (!selectedPersona || !draft.name.trim()) {
      window.alert("请填写 persona 名称。");
      return false;
    }

    setSaving(true);
    try {
      const savedProject = await updatePersona(currentProject._id, currentProject.user_id, selectedPersona.persona_id, {
        name: draft.name.trim(),
        gender: draft.gender.trim(),
        age_range: draft.age_range.trim(),
        preferences: draft.preferences.trim(),
        platform_context: draft.platform_context.trim(),
        ad_sensitivity: draft.ad_sensitivity,
        behavior: draft.behavior.trim(),
        trust_trigger: listFromText(draft.trust_trigger),
        reject_trigger: listFromText(draft.reject_trigger)
      });
      setProject(savedProject);
      const nextDraft = personaToDraft(
        savedProject.personas.find((persona) => persona.persona_id === selectedPersona.persona_id) ?? selectedPersona
      );
      setDraft(nextDraft);
      setBaselineDraft(nextDraft);
      return true;
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "保存失败");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function handleAddPersona() {
    setCreating(true);
    try {
      const savedProject = await createPersona(currentProject._id, currentProject.user_id, {
        name: "New Persona",
        icon: randomPersonaEmoji(),
        ad_sensitivity: "medium"
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
      window.alert(error instanceof Error ? error.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function handleDeletePersona(personaId: string) {
    if (!window.confirm("确定删除这个 persona 吗？")) return;

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
      window.alert(error instanceof Error ? error.message : "删除失败");
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
      window.alert(error instanceof Error ? error.message : "应用失败");
    }
  }

  function handleClose() {
    if (isDirty && !window.confirm("有未保存修改，确定关闭吗？")) return;
    onClose();
  }

  return (
    <div className="persona-overlay" role="presentation">
      <button aria-label="关闭 Persona 面板" className="persona-overlay-backdrop" onClick={handleClose} type="button" />
      <section aria-labelledby="persona-panel-title" aria-modal="true" className="persona-panel" role="dialog">
        <button aria-label="关闭" className="persona-panel-close" onClick={handleClose} type="button">
          <IconClose />
        </button>

        <header className="persona-panel-header">
          <div className="persona-panel-heading">
            <h1 className="persona-panel-title" id="persona-panel-title">
              Persona Management
            </h1>
            <p className="persona-panel-subtitle">
              Define and refine your target audience profiles to optimize BrandVideo&apos;s engagement feedback loop.
            </p>
          </div>
          <button className="persona-add-btn" disabled={creating} onClick={handleAddPersona} type="button">
            <IconPlus />
            Add New Persona
          </button>
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
                        aria-label={`删除 ${persona.name}`}
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
                <div className="persona-empty">暂无 persona，点击右上角新建。</div>
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
                  <label className="persona-field persona-field-full">
                    <span>Name</span>
                    <input onChange={(event) => updateDraft("name", event.target.value)} value={draft.name} />
                  </label>

                  <label className="persona-field">
                    <span>Demographics (Gender / Age)</span>
                    <div className="persona-demographics">
                      <select onChange={(event) => updateDraft("gender", event.target.value)} value={draft.gender}>
                        <option value="">Select</option>
                        <option value="Female">Female</option>
                        <option value="Male">Male</option>
                        <option value="Non-binary">Non-binary</option>
                        <option value="Other">Other</option>
                      </select>
                      <input
                        onChange={(event) => updateDraft("age_range", event.target.value)}
                        placeholder="24-30, Urban"
                        value={draft.age_range}
                      />
                    </div>
                  </label>

                  <label className="persona-field persona-field-full">
                    <span>Preferences (Interests &amp; Hobbies)</span>
                    <input
                      onChange={(event) => updateDraft("preferences", event.target.value)}
                      value={draft.preferences}
                    />
                  </label>

                  <label className="persona-field">
                    <span>Consumption Platforms</span>
                    <input
                      onChange={(event) => updateDraft("platform_context", event.target.value)}
                      value={draft.platform_context}
                    />
                  </label>

                  <div className="persona-field">
                    <span>Ad Sensitivity</span>
                    <div className="persona-segmented">
                      {(["low", "medium", "high"] as const).map((level) => (
                        <button
                          className={draft.ad_sensitivity === level ? "active" : ""}
                          key={level}
                          onClick={() => updateDraft("ad_sensitivity", level)}
                          type="button"
                        >
                          {level[0].toUpperCase() + level.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>

                  <label className="persona-field persona-field-full">
                    <span>Content Scenarios</span>
                    <textarea onChange={(event) => updateDraft("behavior", event.target.value)} rows={3} value={draft.behavior} />
                  </label>

                  <label className="persona-field">
                    <span>Trust Triggers</span>
                    <textarea
                      onChange={(event) => updateDraft("trust_trigger", event.target.value)}
                      rows={4}
                      value={draft.trust_trigger}
                    />
                  </label>

                  <label className="persona-field">
                    <span>Friction / Churn Triggers</span>
                    <textarea
                      onChange={(event) => updateDraft("reject_trigger", event.target.value)}
                      rows={4}
                      value={draft.reject_trigger}
                    />
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
              <div className="persona-editor-empty">选择或新建一个 persona 开始配置。</div>
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
