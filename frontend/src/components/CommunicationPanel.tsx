"use client";

import { useMemo, useState } from "react";

import { generateNegotiationPlan, toggleCommunicationSupport } from "@/lib/api";
import { useAppStore } from "@/store/appStore";

type CommunicationTab = "argue" | "plan";

type ArgueItem = {
  id: string;
  title: string;
  content: string;
  rowId: string;
  columnId: string;
};

type CommunicationPanelProps = {
  open: boolean;
  onClose: () => void;
  projectId?: string;
  userId?: string;
};

export function CommunicationPanel({ open, onClose, projectId, userId }: CommunicationPanelProps) {
  const project = useAppStore((state) => state.project);
  const setProject = useAppStore((state) => state.setProject);
  const [tab, setTab] = useState<CommunicationTab>("argue");
  const [argumentBrief, setArgumentBrief] = useState("");
  const [generating, setGenerating] = useState(false);
  const [busyNodeId, setBusyNodeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const argueItems = useMemo(() => {
    const queueItems = project?.communication_support_queue ?? [];
    const queue = new Set(queueItems);
    const items: ArgueItem[] = [];
    const includedRowIds = new Set<string>();

    for (const node of project?.rationale_nodes ?? []) {
      if (node.source_type !== "brand_feedback") continue;
      const inList = Boolean(node.in_communication_support_queue) || queue.has(node.node_id);
      if (!inList) continue;

      const ref = node.linked_script_refs?.[0];
      if (!ref?.row_id || !ref.column_id) continue;
      includedRowIds.add(ref.row_id);
      items.push({
        id: node.node_id,
        title: node.title,
        content: node.content || node.title,
        rowId: ref.row_id,
        columnId: ref.column_id,
      });
    }

    const feedbackColumn = project?.current_script.columns.find((column) => column.key === "feedback");
    if (!feedbackColumn) return items;

    for (const rowId of queueItems) {
      if (includedRowIds.has(rowId)) continue;
      const row = project?.current_script.rows.find((item) => item.row_id === rowId);
      const cell = row?.cells.find((item) => item.column_id === feedbackColumn.column_id);
      const content = cell?.value.trim();
      if (!content) continue;
      items.push({
        id: rowId,
        title: content.slice(0, 120),
        content,
        rowId,
        columnId: feedbackColumn.column_id,
      });
    }

    return items;
  }, [project?.current_script.columns, project?.current_script.rows, project?.rationale_nodes, project?.communication_support_queue]);

  const considerationCount = project?.consideration_queue?.length ?? 0;
  const plan = project?.negotiation_preparation ?? null;
  const hasArgumentBrief = argumentBrief.trim().length > 0;

  if (!open) return null;

  async function handleRemove(item: ArgueItem) {
    if (!projectId || !userId || busyNodeId) return;
    setBusyNodeId(item.id);
    setError(null);
    try {
      const updated = await toggleCommunicationSupport(projectId, userId, item.rowId, item.columnId, false);
      setProject(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update list");
    } finally {
      setBusyNodeId(null);
    }
  }

  async function handleGenerate() {
    if (!projectId || !userId || generating) return;
    setGenerating(true);
    setError(null);
    try {
      const { project: updated } = await generateNegotiationPlan(
        projectId,
        userId,
        hasArgumentBrief ? argumentBrief.trim() : undefined
      );
      setProject(updated);
      setTab("plan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate negotiation plan");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <>
      <button
        className="glacier-backdrop comm-dialog-backdrop"
        onClick={onClose}
        type="button"
        aria-label="Close Communication panel"
      />
      <aside className="glacier-assistant comm-dialog" aria-label="Communication & Negotiation">
        <header className="glacier-header">
          <div className="glacier-header-top">
            <div className="glacier-title-row">
              <span className="glacier-icon-badge" aria-hidden="true">
                <IconHandshake />
              </span>
              <span className="glacier-title">Communication</span>
            </div>
            <button className="glacier-close" onClick={onClose} type="button" aria-label="Close">
              <IconClose />
            </button>
          </div>
          <div className="glacier-tabs" role="tablist" aria-label="Communication views">
            <button
              className={`glacier-tab ${tab === "argue" ? "active" : ""}`}
              onClick={() => setTab("argue")}
              role="tab"
              aria-selected={tab === "argue"}
              type="button"
            >
              Argue Input
              {argueItems.length > 0 ? (
                <span className="map-right-tab-badge">{argueItems.length}</span>
              ) : null}
            </button>
            <button
              className={`glacier-tab ${tab === "plan" ? "active" : ""}`}
              onClick={() => setTab("plan")}
              role="tab"
              aria-selected={tab === "plan"}
              type="button"
            >
              Communication Plan
            </button>
          </div>
        </header>

        <div className="glacier-body app-scrollbar">
          {error ? <p className="glacier-stream-error">{error}</p> : null}

          {tab === "argue" ? (
            <div className="comm-list">
              <p className="comm-hint">
                Add the point you want to discuss with the brand. You can also mark feedback with "Argue" in the Script
                Editor.
              </p>
              <div className="comm-input-grid">
                <section className="comm-reference-col" aria-label="Referenced brand feedback">
                  <h3 className="comm-column-title">Referenced brand feedback</h3>
                  {argueItems.length === 0 ? (
                    <p className="comm-empty">
                      No script feedback marked yet. You can still generate from the text on the right.
                    </p>
                  ) : (
                    <div className="comm-card-list app-scrollbar">
                      {argueItems.map((item) => {
                        return (
                          <article className="comm-card" key={item.id}>
                            <div className="comm-card-body">
                              <p className="comm-card-text">{item.content}</p>
                            </div>
                            <button
                              aria-label="Remove from argue list"
                              className="requirement-delete-btn"
                              onClick={() => void handleRemove(item)}
                              disabled={busyNodeId === item.id}
                              type="button"
                            >
                              <IconTrash />
                            </button>
                          </article>
                        );
                      })}
                    </div>
                  )}
                </section>
                <section className="comm-draft-col" aria-label="Creator argument brief">
                  <label className="comm-brief-field">
                    <span>Your argument brief</span>
                    <textarea
                      aria-label="Describe what you want to argue with the brand"
                      onChange={(event) => setArgumentBrief(event.target.value)}
                      placeholder="Example: I want to keep the slower opening because it makes the product scene feel more natural, but I can accept adding one clearer product close-up."
                      rows={12}
                      value={argumentBrief}
                    />
                  </label>
                </section>
              </div>
            </div>
          ) : (
            <div className="comm-plan">
              {plan ? (
                <>
                  <section className="comm-plan-section">
                    <h3 className="comm-plan-title">{plan.title}</h3>
                    {plan.design_intent ? <p className="comm-plan-intent">{plan.design_intent}</p> : null}
                  </section>

                  <section className="comm-plan-section">
                    <div className="comm-plan-header-row">
                      <h4 className="comm-plan-subtitle">Reply messages ({plan.open_disputes.length})</h4>
                      <button
                        className="comm-copy-all-btn"
                        onClick={() => {
                          const allReplies = plan.open_disputes
                            .map((d, i) => {
                              const reply = d.reply || d.our_position || d.summary || "(No content)";
                              const feedback = d.brand_feedback || d.summary || `Feedback #${i + 1}`;
                              return `**${i + 1}. ${feedback}**\n${reply}`;
                            })
                            .join("\n\n---\n\n");
                          void navigator.clipboard.writeText(allReplies).then(() => {
                            /* visual feedback handled via button text swap */
                          });
                        }}
                        type="button"
                      >
                        <IconCopy /> Copy all
                      </button>
                    </div>
                    {plan.open_disputes.map((dispute, index) => {
                      // Robust fallback chain: new fields → legacy fields → hardcoded placeholder
                      const replyText = dispute.reply || dispute.our_position || dispute.summary || "(No reply generated — please regenerate)";
                      const feedbackText = dispute.brand_feedback || dispute.summary || `Feedback #${index + 1}`;
                      const fallbackText = dispute.fallback || dispute.acceptable_concession || "";
                      const talkingPoints = dispute.talking_points || [];

                      return (
                        <article className="comm-dispute" key={dispute.issue_node_id || index}>
                          <div className="comm-dispute-head">
                            <span className="comm-dispute-index">#{index + 1}</span>
                            <span className="comm-dispute-feedback-label">{feedbackText}</span>
                          </div>

                          <div className="comm-dispute-reply-box">
                            <div className="comm-dispute-reply-header">
                              <span className="comm-dispute-label">Reply</span>
                              <button
                                className="comm-copy-btn"
                                onClick={() => void navigator.clipboard.writeText(replyText)}
                                type="button"
                                title="Copy reply"
                              >
                                <IconCopy />
                              </button>
                            </div>
                            <p className="comm-dispute-reply-text">{replyText}</p>
                          </div>

                          {fallbackText && fallbackText !== "暂不让步" && fallbackText !== "无" ? (
                            <p className="comm-dispute-fallback">
                              <span className="comm-dispute-label">Fallback</span>
                              {fallbackText}
                            </p>
                          ) : null}

                          {talkingPoints.length > 0 ? (
                            <div className="comm-dispute-points">
                              <span className="comm-dispute-label">Key points</span>
                              <ul className="comm-plan-ul">
                                {talkingPoints.map((point, pointIndex) => (
                                  <li key={pointIndex}>{point}</li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </article>
                      );
                    })}
                  </section>
                </>
              ) : (
                <p className="comm-empty">
                  No negotiation plan yet. Add feedback to the Argue List, then generate a plan that aggregates the
                  brand, audience, and creator perspectives.
                </p>
              )}
            </div>
          )}
        </div>

        <footer className="glacier-input-area comm-footer">
          <button
            className="comm-generate-btn"
            onClick={() => void handleGenerate()}
            disabled={generating || (argueItems.length === 0 && !hasArgumentBrief)}
            type="button"
          >
            {generating ? "Generating…" : plan ? "Regenerate Communication Plan" : "Generate Communication Plan"}
          </button>
        </footer>
      </aside>
    </>
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

function IconCopy() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
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
