"use client";

import { useEffect, useMemo, useState } from "react";

import { parseBriefStream, updateBrandRequirements } from "@/lib/api";
import {
  createEmptyInsight,
  insightsFromProject,
  toApiBrandInsights
} from "@/lib/brandRequirements";
import type { BrandInsight, BrandInsightCategory, BrandInsightConfidence } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

type RequirementsPanelProps = {
  open: boolean;
  onClose: () => void;
};

type RequirementTab = "explicit" | "implicit";

function listsEqual(a: BrandInsight[], b: BrandInsight[]) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function tabToCategory(tab: RequirementTab): BrandInsightCategory {
  return tab === "explicit" ? "explicit_requirement" : "implicit_requirement";
}

export function RequirementsPanel({ open, onClose }: RequirementsPanelProps) {
  const { project, setProject } = useAppStore();
  const [activeTab, setActiveTab] = useState<RequirementTab>("explicit");
  const [explicit, setExplicit] = useState<BrandInsight[]>([]);
  const [implicit, setImplicit] = useState<BrandInsight[]>([]);
  const [baselineExplicit, setBaselineExplicit] = useState<BrandInsight[]>([]);
  const [baselineImplicit, setBaselineImplicit] = useState<BrandInsight[]>([]);
  const [saving, setSaving] = useState(false);
  const [parsing, setParsing] = useState(false);

  const hasBrief = Boolean(project?.brief.text?.trim() || project?.brief.filename);
  const hasParsedBrief = project?.brief.parse_status === "parsed";
  const isDirty = useMemo(
    () => !listsEqual(explicit, baselineExplicit) || !listsEqual(implicit, baselineImplicit),
    [explicit, implicit, baselineExplicit, baselineImplicit]
  );

  useEffect(() => {
    if (!open || !project) return;
    const { explicit: nextExplicit, implicit: nextImplicit } = insightsFromProject(project);
    setExplicit(nextExplicit);
    setImplicit(nextImplicit);
    setBaselineExplicit(nextExplicit);
    setBaselineImplicit(nextImplicit);
    setActiveTab("explicit");
  }, [open, project?._id, project?.brand_insights, project?.updated_at]);

  if (!open || !project) return null;

  const currentProject = project;
  const activeList = activeTab === "explicit" ? explicit : implicit;
  const setActiveList = activeTab === "explicit" ? setExplicit : setImplicit;

  function updateInsight(insightId: string, patch: Partial<BrandInsight>) {
    setActiveList((items) =>
      items.map((item) => (item.insight_id === insightId ? { ...item, ...patch } : item))
    );
  }

  function addInsight() {
    setActiveList((items) => [...items, createEmptyInsight(tabToCategory(activeTab))]);
  }

  function removeInsight(insightId: string) {
    setActiveList((items) => items.filter((item) => item.insight_id !== insightId));
  }

  async function handleSave() {
    const payloadInsights = toApiBrandInsights([...explicit, ...implicit]);

    setSaving(true);
    try {
      const savedProject = await updateBrandRequirements(currentProject._id, currentProject.user_id, {
        brand_insights: payloadInsights
      });
      setProject(savedProject);
      const next = insightsFromProject(savedProject);
      setExplicit(next.explicit);
      setImplicit(next.implicit);
      setBaselineExplicit(next.explicit);
      setBaselineImplicit(next.implicit);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleParseBrief() {
    setParsing(true);
    try {
      await parseBriefStream(currentProject._id, currentProject.user_id, (event) => {
        if (event.type === "done") {
          setProject(event.project);
          const parsed = insightsFromProject(event.project);

          const parsedExplicitIds = new Set(parsed.explicit.map((r) => r.insight_id));
          const parsedImplicitIds = new Set(parsed.implicit.map((r) => r.insight_id));
          const pendingExplicit = explicit.filter(
            (r) => r.created_by === "user" && !parsedExplicitIds.has(r.insight_id)
          );
          const pendingImplicit = implicit.filter(
            (r) => r.created_by === "user" && !parsedImplicitIds.has(r.insight_id)
          );

          const mergedExplicit = [...parsed.explicit, ...pendingExplicit];
          const mergedImplicit = [...parsed.implicit, ...pendingImplicit];

          setExplicit(mergedExplicit);
          setImplicit(mergedImplicit);
          setBaselineExplicit(parsed.explicit);
          setBaselineImplicit(parsed.implicit);
        } else if (event.type === "error") {
          window.alert(event.message);
        }
      });
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Brief parse failed");
    } finally {
      setParsing(false);
    }
  }

  function handleClose() {
    if (isDirty && !window.confirm("You have unsaved requirement changes. Close anyway?")) return;
    onClose();
  }

  return (
    <div className="persona-overlay" role="presentation">
      <button aria-label="Close requirements panel" className="persona-overlay-backdrop" onClick={handleClose} type="button" />
      <section
        aria-labelledby="requirements-panel-title"
        aria-modal="true"
        className="persona-panel requirements-panel"
        role="dialog"
      >
        <button aria-label="Close" className="persona-panel-close" onClick={handleClose} type="button">
          <IconClose />
        </button>

        <header className="persona-panel-header requirements-panel-header">
          <div className="persona-panel-heading">
            <h1 className="persona-panel-title" id="requirements-panel-title">
              Brand Requirements
            </h1>
            <p className="persona-panel-subtitle">
              Explicit and implicit brand needs inferred from your Brief. Edit here to keep agents aligned.
            </p>
          </div>
          <div className="persona-panel-actions">
            <button
              className="persona-add-btn persona-add-btn-secondary"
              disabled={parsing || !hasBrief}
              onClick={handleParseBrief}
              title={hasBrief ? undefined : "Upload a Brief first"}
              type="button"
            >
              {parsing ? "Parsing…" : hasParsedBrief ? "Re-parse Brief" : "Parse from Brief"}
            </button>
            <button className="persona-add-btn" disabled={saving || !isDirty} onClick={handleSave} type="button">
              {saving ? "Saving…" : "Save Changes"}
            </button>
          </div>
        </header>

        <div className="requirements-tabs" role="tablist" aria-label="Requirement type">
          <button
            className={`requirements-tab ${activeTab === "explicit" ? "active" : ""}`}
            onClick={() => setActiveTab("explicit")}
            role="tab"
            aria-selected={activeTab === "explicit"}
            type="button"
          >
            Explicit
            <span className="requirements-tab-count">{explicit.length}</span>
          </button>
          <button
            className={`requirements-tab ${activeTab === "implicit" ? "active" : ""}`}
            onClick={() => setActiveTab("implicit")}
            role="tab"
            aria-selected={activeTab === "implicit"}
            type="button"
          >
            Implicit
            <span className="requirements-tab-count">{implicit.length}</span>
          </button>
        </div>

        <div className="requirements-panel-body">
          {activeList.length === 0 ? (
            <p className="requirements-empty">
              {!hasParsedBrief
                ? hasBrief
                  ? 'Brief uploaded. Click "Parse from Brief" above to let the Brand Agent populate requirements here.'
                  : "Upload a Brief first, then click \u201CParse from Brief\u201D to populate requirements here."
                : `No ${activeTab === "explicit" ? "explicit" : "implicit"} requirements yet. Add one below or re-parse your Brief.`}
            </p>
          ) : (
            <ul className="requirements-list">
              {activeList.map((item, index) => (
                <li className="requirement-card" key={item.insight_id}>
                  <div className="requirement-card-header">
                    <span className="requirement-card-index">#{index + 1}</span>
                    <label className="requirement-confidence-label">
                      Confidence
                      <select
                        className="requirement-confidence-select"
                        onChange={(event) =>
                          updateInsight(item.insight_id, {
                            confidence: event.target.value as BrandInsightConfidence
                          })
                        }
                        value={item.confidence}
                      >
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                      </select>
                    </label>
                    <button
                      aria-label="Delete requirement"
                      className="requirement-delete-btn"
                      onClick={() => removeInsight(item.insight_id)}
                      type="button"
                    >
                      <IconTrash />
                    </button>
                  </div>
                  <label className="requirement-field">
                    <span>Title</span>
                    <input
                      onChange={(event) => updateInsight(item.insight_id, { title: event.target.value })}
                      placeholder="Short label for this requirement"
                      type="text"
                      value={item.title}
                    />
                  </label>
                  <label className="requirement-field">
                    <span>Content</span>
                    <textarea
                      onChange={(event) => updateInsight(item.insight_id, { content: event.target.value })}
                      placeholder="Describe the brand requirement…"
                      rows={3}
                      value={item.content}
                    />
                  </label>
                  <label className="requirement-field">
                    <span>Reason</span>
                    <textarea
                      onChange={(event) => updateInsight(item.insight_id, { reason: event.target.value })}
                      placeholder="Why this requirement exists (from Brief or inference)"
                      rows={2}
                      value={item.reason}
                    />
                  </label>
                </li>
              ))}
            </ul>
          )}

          <button className="requirements-add-btn" onClick={addInsight} type="button">
            <IconPlus />
            Add {activeTab === "explicit" ? "explicit" : "implicit"} requirement
          </button>
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

function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 6h18" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}
