"use client";

import { useMemo, useState } from "react";

import { generateNegotiationPlan, toggleCommunicationSupport } from "@/lib/api";
import type { NegotiationPreparation, RationaleNode } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

// ─── Dev mock ────────────────────────────────────────────────────────────────
const USE_MOCK = process.env.NODE_ENV === "development";

const MOCK_ARGUE_NODES: RationaleNode[] = [
  {
    node_id: "mock-1",
    project_id: "mock",
    node_type: "issue",
    title: "品牌色调偏冷",
    content: "整体视频色调偏冷蓝，与品牌暖橙色系不符，建议增加暖色调镜头以强化品牌识别。",
    source_type: "brand_feedback",
    source_perspective: "brand",
    in_communication_support_queue: true,
    linked_script_refs: [{ row_id: "第 2 幕", column_id: "col-visual" }],
    created_by: "brand",
    updated_at: new Date().toISOString(),
  },
  {
    node_id: "mock-2",
    project_id: "mock",
    node_type: "issue",
    title: "产品露出时长不足",
    content: "产品在第 3–5 幕出镜时间过短，品牌方要求至少 8 秒清晰展示。",
    source_type: "brand_feedback",
    source_perspective: "brand",
    in_communication_support_queue: true,
    linked_script_refs: [{ row_id: "第 4 幕", column_id: "col-action" }],
    created_by: "brand",
    updated_at: new Date().toISOString(),
  },
];

const MOCK_PLAN: NegotiationPreparation = {
  prep_id: "mock-plan-1",
  project_id: "mock",
  title: "沟通准备方案 · 第一稿",
  based_on_script_version_id: null,
  design_intent:
    "本视频以「真实生活方式」为创作核心，色调的选取服务于叙事氛围而非品牌视觉规范，两者可以并存。",
  satisfied_brand_needs: [
    "已在片尾 10 秒完整展示产品及 Logo",
    "口播台词已包含全部品牌 Slogan",
    "视频封面使用品牌主色进行了突出处理",
  ],
  open_disputes: [
    {
      issue_node_id: "mock-1",
      summary: "视频整体色调与品牌暖橙色系存在偏差",
      our_position:
        "色调设计服务于「傍晚咖啡馆」叙事场景，冷暖对比是有意为之的情绪节奏。",
      acceptable_concession:
        "可在第 1 幕片头增加 2 秒暖色调品牌卡，强化品牌识别。",
      non_negotiable_line:
        "主体叙事段落的色调调整将破坏整体观感，不予修改。",
      talking_points: [
        "冷色调前段与暖色调产品特写形成对比，令产品更突出",
        "同类竞品案例亦采用类似的色彩策略",
        "可通过后期调色在不影响叙事的前提下微调色温 +200K",
      ],
      related_node_ids: [],
      related_script_refs: [],
    },
    {
      issue_node_id: "mock-2",
      summary: "产品出镜时长未达品牌方 8 秒要求",
      our_position:
        "过长的产品镜头会使视频显得广告感过重，影响完播率。",
      acceptable_concession:
        "可将第 4 幕产品特写从 3 秒延长至 5 秒，并在第 6 幕补充一个 2 秒的产品 B-Roll。",
      non_negotiable_line: "单次产品镜头不超过 5 秒，总时长不超过 10 秒。",
      talking_points: [
        "数据显示超过 8 秒的产品镜头会导致滑走率上升 15%",
        "将产品融入真实使用场景比静态展示更有说服力",
        "目前已有 3 处产品自然出镜，累计约 6 秒",
      ],
      related_node_ids: [],
      related_script_refs: [],
    },
  ],
  recommended_communication_order: ["mock-1", "mock-2"],
  related_issue_ids: ["mock-1", "mock-2"],
  status: "draft",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};
// ─────────────────────────────────────────────────────────────────────────────

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
  const [argumentBrief, setArgumentBrief] = useState("");
  const [generating, setGenerating] = useState(false);
  const [busyNodeId, setBusyNodeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const argueNodes = useMemo(() => {
    const queue = new Set(project?.communication_support_queue ?? []);
    const real = (project?.rationale_nodes ?? []).filter(
      (node) =>
        node.source_type === "brand_feedback" &&
        (Boolean(node.in_communication_support_queue) || queue.has(node.node_id))
    );
    return USE_MOCK && real.length === 0 ? MOCK_ARGUE_NODES : real;
  }, [project?.rationale_nodes, project?.communication_support_queue]);

  const considerationCount =
    USE_MOCK && (project?.consideration_queue?.length ?? 0) === 0
      ? 3
      : (project?.consideration_queue?.length ?? 0);
  const plan =
    USE_MOCK && project?.negotiation_preparation == null
      ? MOCK_PLAN
      : (project?.negotiation_preparation ?? null);
  const hasArgumentBrief = argumentBrief.trim().length > 0;

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

  const disputeTitleById = new Map(argueNodes.map((node) => [node.node_id, node.title]));

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
              Argue Input ({argueNodes.length})
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
                Add the point you want to discuss with the brand. You can also mark feedback with "Argue" in the Script
                Editor, then generate a plan grounded in your TO BE CONSIDERED stances ({considerationCount}).
              </p>
              <div className="comm-input-grid">
                <section className="comm-reference-col" aria-label="Referenced brand feedback">
                  <h3 className="comm-column-title">Referenced brand feedback</h3>
                  {argueNodes.length === 0 ? (
                    <p className="comm-empty">
                      No script feedback marked yet. You can still generate from the text on the right.
                    </p>
                  ) : (
                    <div className="comm-card-list">
                      {argueNodes.map((node) => {
                        const ref = node.linked_script_refs?.[0];
                        return (
                          <article className="comm-card" key={node.node_id}>
                            <div className="comm-card-body">
                              <p className="comm-card-text">{node.content || node.title}</p>
                              {ref?.row_id ? <span className="comm-card-meta">Scene row: {ref.row_id}</span> : null}
                            </div>
                            <button
                              aria-label="Remove from argue list"
                              className="requirement-delete-btn"
                              onClick={() => void handleRemove(node)}
                              disabled={busyNodeId === node.node_id}
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
            disabled={generating || (argueNodes.length === 0 && !hasArgumentBrief)}
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

function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 6h18" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}
