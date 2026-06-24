"use client";

import { useMemo, useState } from "react";

import { generateNegotiationPlan, toggleCommunicationSupport } from "@/lib/api";
import type { RationaleNode } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

type CommunicationTab = "argue" | "plan";

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
  const [generating, setGenerating] = useState(false);
  const [busyNodeId, setBusyNodeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const argueNodes = useMemo(() => {
    const queue = new Set(project?.communication_support_queue ?? []);
    return (project?.rationale_nodes ?? []).filter(
      (node) =>
        node.source_type === "brand_feedback" &&
        (Boolean(node.in_communication_support_queue) || queue.has(node.node_id))
    );
  }, [project?.rationale_nodes, project?.communication_support_queue]);

  const considerationCount = project?.consideration_queue?.length ?? 0;
  const plan = project?.negotiation_preparation ?? null;

  if (!open) return null;

  async function handleRemove(node: RationaleNode) {
    if (!projectId || !userId || busyNodeId) return;
    const ref = node.linked_script_refs?.[0];
    if (!ref?.row_id || !ref.column_id) return;
    setBusyNodeId(node.node_id);
    setError(null);
    try {
      const updated = await toggleCommunicationSupport(projectId, userId, ref.row_id, ref.column_id, false);
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
      const { project: updated } = await generateNegotiationPlan(projectId, userId);
      setProject(updated);
      setTab("plan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate negotiation plan");
    } finally {
      setGenerating(false);
    }
  }

  const disputeTitleById = new Map(argueNodes.map((node) => [node.node_id, node.title]));

  return (
    <>
      <button className="glacier-backdrop" onClick={onClose} type="button" aria-label="Close Communication panel" />
      <aside className="glacier-assistant" aria-label="Communication & Negotiation">
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
              Argue List ({argueNodes.length})
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

        <div className="glacier-body">
          {error ? <p className="glacier-stream-error">{error}</p> : null}

          {tab === "argue" ? (
            <div className="comm-list">
              <p className="comm-hint">
                Brand feedback you chose to argue. Mark a feedback with “Argue” in the Script Editor to add it here, then
                generate a negotiation plan grounded in your TO BE CONSIDERED stances ({considerationCount}).
              </p>
              {argueNodes.length === 0 ? (
                <p className="comm-empty">No feedback on the communication support list yet.</p>
              ) : (
                argueNodes.map((node) => {
                  const ref = node.linked_script_refs?.[0];
                  return (
                    <article className="comm-card" key={node.node_id}>
                      <div className="comm-card-body">
                        <p className="comm-card-text">{node.content || node.title}</p>
                        {ref?.row_id ? <span className="comm-card-meta">Scene row: {ref.row_id}</span> : null}
                      </div>
                      <button
                        className="comm-card-remove"
                        onClick={() => void handleRemove(node)}
                        disabled={busyNodeId === node.node_id}
                        type="button"
                      >
                        {busyNodeId === node.node_id ? "…" : "Remove"}
                      </button>
                    </article>
                  );
                })
              )}
            </div>
          ) : (
            <div className="comm-plan">
              {plan ? (
                <>
                  <section className="comm-plan-section">
                    <h3 className="comm-plan-title">{plan.title}</h3>
                    {plan.design_intent ? <p className="comm-plan-intent">{plan.design_intent}</p> : null}
                  </section>

                  {plan.satisfied_brand_needs.length > 0 ? (
                    <section className="comm-plan-section">
                      <h4 className="comm-plan-subtitle">Satisfied brand needs</h4>
                      <ul className="comm-plan-ul">
                        {plan.satisfied_brand_needs.map((need, index) => (
                          <li key={index}>{need}</li>
                        ))}
                      </ul>
                    </section>
                  ) : null}

                  <section className="comm-plan-section">
                    <h4 className="comm-plan-subtitle">Open disputes ({plan.open_disputes.length})</h4>
                    {plan.open_disputes.map((dispute, index) => (
                      <article className="comm-dispute" key={dispute.issue_node_id || index}>
                        <p className="comm-dispute-summary">{dispute.summary}</p>
                        {dispute.our_position ? (
                          <p className="comm-dispute-row">
                            <span className="comm-dispute-label">Our position</span>
                            {dispute.our_position}
                          </p>
                        ) : null}
                        {dispute.talking_points.length > 0 ? (
                          <div className="comm-dispute-row">
                            <span className="comm-dispute-label">Talking points</span>
                            <ul className="comm-plan-ul">
                              {dispute.talking_points.map((point, pointIndex) => (
                                <li key={pointIndex}>{point}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {dispute.acceptable_concession ? (
                          <p className="comm-dispute-row">
                            <span className="comm-dispute-label">Concession</span>
                            {dispute.acceptable_concession}
                          </p>
                        ) : null}
                        {dispute.non_negotiable_line ? (
                          <p className="comm-dispute-row comm-dispute-line">
                            <span className="comm-dispute-label">Bottom line</span>
                            {dispute.non_negotiable_line}
                          </p>
                        ) : null}
                      </article>
                    ))}
                  </section>

                  {plan.recommended_communication_order.length > 0 ? (
                    <section className="comm-plan-section">
                      <h4 className="comm-plan-subtitle">Recommended order</h4>
                      <ol className="comm-plan-ol">
                        {plan.recommended_communication_order.map((nodeId, index) => (
                          <li key={`${nodeId}-${index}`}>{disputeTitleById.get(nodeId) ?? nodeId}</li>
                        ))}
                      </ol>
                    </section>
                  ) : null}
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
            disabled={generating || argueNodes.length === 0}
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

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
