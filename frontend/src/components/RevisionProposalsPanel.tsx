"use client";

import { useEffect, useMemo, useState } from "react";

import { applyModificationSchemeHunks } from "@/lib/api";
import {
  buildPreviewTable,
  listSchemePreviewCells,
  schemeDecisionSummary
} from "@/lib/schemePreview";
import { isStaleStatus } from "@/lib/stale";
import type { HunkDecision, ModificationScheme, ModificationSchemeDirection, Script } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

const DIRECTION_LABELS: Record<ModificationSchemeDirection, string> = {
  conservative: "保守 · 品牌优先",
  balanced: "平衡",
  creator_led: "创作者主导",
  audience_friendly: "观众友好",
  custom: "自定义"
};

type PreviewMode = "all_proposed" | "accepted_only";

type RevisionProposalsPanelProps = {
  projectId: string;
  userId: string;
};

export function RevisionProposalsPanel({ projectId, userId }: RevisionProposalsPanelProps) {
  const project = useAppStore((state) => state.project);
  const script = useAppStore((state) => state.script);
  const setProject = useAppStore((state) => state.setProject);
  const setScript = useAppStore((state) => state.setScript);

  const schemes = project?.modification_schemes ?? [];
  const schemesStale = isStaleStatus(project?.stale?.modification_schemes);

  const [selectedSchemeId, setSelectedSchemeId] = useState<string | null>(null);
  const [hunkDecisions, setHunkDecisions] = useState<Record<string, HunkDecision>>({});
  const [previewMode, setPreviewMode] = useState<PreviewMode>("all_proposed");
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const selectedScheme = useMemo(
    () => schemes.find((scheme) => scheme.scheme_id === selectedSchemeId) ?? null,
    [schemes, selectedSchemeId]
  );

  const activeScript = script ?? project?.current_script ?? null;

  const summary = useMemo(
    () => (selectedScheme ? schemeDecisionSummary(selectedScheme, hunkDecisions) : null),
    [selectedScheme, hunkDecisions]
  );

  const previewTable = useMemo(() => {
    if (!activeScript || !selectedScheme) return [];
    return buildPreviewTable(activeScript, selectedScheme, hunkDecisions, previewMode);
  }, [activeScript, selectedScheme, hunkDecisions, previewMode]);

  useEffect(() => {
    if (!selectedSchemeId && schemes.length) {
      setSelectedSchemeId(schemes[schemes.length - 1].scheme_id);
    }
  }, [schemes, selectedSchemeId]);

  useEffect(() => {
    if (!selectedScheme) {
      setHunkDecisions({});
      return;
    }
    const initial: Record<string, HunkDecision> = {};
    for (const hunk of selectedScheme.hunks) {
      initial[hunk.hunk_id] = null;
    }
    setHunkDecisions(initial);
    setPreviewMode("all_proposed");
  }, [selectedScheme?.scheme_id]);

  const acceptedHunkIds = useMemo(
    () => Object.entries(hunkDecisions).filter(([, value]) => value === true).map(([id]) => id),
    [hunkDecisions]
  );

  const rejectedHunkIds = useMemo(
    () => Object.entries(hunkDecisions).filter(([, value]) => value === false).map(([id]) => id),
    [hunkDecisions]
  );

  async function handleApplyPartial() {
    if (!selectedScheme || !acceptedHunkIds.length) return;
    setApplying(true);
    setError(null);
    setStatusMessage(null);
    try {
      const updated = await applyModificationSchemeHunks(
        projectId,
        userId,
        selectedScheme.scheme_id,
        acceptedHunkIds,
        rejectedHunkIds
      );
      setProject(updated);
      setScript(updated.current_script);
      const total = selectedScheme.hunks.length;
      const label =
        acceptedHunkIds.length >= total
          ? "已全部写入脚本"
          : `已部分写入（${acceptedHunkIds.length}/${total} 处），可在版本历史中回退`;
      setStatusMessage(label);
    } catch (err) {
      setError(err instanceof Error ? err.message : "写入脚本失败");
    } finally {
      setApplying(false);
    }
  }

  function acceptAllHunks() {
    if (!selectedScheme) return;
    const next: Record<string, HunkDecision> = {};
    for (const hunk of selectedScheme.hunks) {
      next[hunk.hunk_id] = true;
    }
    setHunkDecisions(next);
    setPreviewMode("accepted_only");
  }

  function rejectAllHunks() {
    if (!selectedScheme) return;
    const next: Record<string, HunkDecision> = {};
    for (const hunk of selectedScheme.hunks) {
      next[hunk.hunk_id] = false;
    }
    setHunkDecisions(next);
    setPreviewMode("accepted_only");
  }

  function setHunkDecision(hunkId: string, decision: HunkDecision) {
    setHunkDecisions((prev) => ({ ...prev, [hunkId]: decision }));
  }

  return (
    <>
      <div className="glacier-plans-list">
        {schemesStale ? (
          <p className="glacier-plans-stale-banner">
            脚本已变更。请在 Chat 请 Coordinator「重新生成修改方案」，再预览并写入。
          </p>
        ) : null}
        {error ? <p className="glacier-stream-error">{error}</p> : null}
        {statusMessage ? <p className="glacier-plans-status">{statusMessage}</p> : null}

        {!schemes.length ? (
          <p className="glacier-plans-placeholder">
            尚无修改方案。在 Chat 告诉 Coordinator：「请生成多方向修改方案」——会在此预览稿子并逐条接受/拒绝，也可只写入部分修改。
          </p>
        ) : null}

        {schemes.map((scheme) => (
          <SchemeCard
            key={scheme.scheme_id}
            active={scheme.scheme_id === selectedSchemeId}
            scheme={scheme}
            onSelect={() => setSelectedSchemeId(scheme.scheme_id)}
          />
        ))}

        {selectedScheme && activeScript ? (
          <>
            <ScriptSchemePreview
              previewMode={previewMode}
              previewTable={previewTable}
              summary={summary}
              onPreviewModeChange={setPreviewMode}
            />
            <SchemeDetail
              scheme={selectedScheme}
              script={activeScript}
              hunkDecisions={hunkDecisions}
              onHunkDecision={setHunkDecision}
            />
          </>
        ) : null}
      </div>

      {selectedScheme?.hunks.length ? (
        <div className="glacier-plans-actions">
          <p className="glacier-plans-actions-hint">
            {summary
              ? `已选 ${summary.accepted} 接受 · ${summary.rejected} 拒绝 · ${summary.pending} 待定（共 ${summary.total} 处）`
              : null}
          </p>
          <div className="glacier-plans-actions-row">
            <button className="glacier-btn glacier-btn--outline" onClick={acceptAllHunks} type="button" disabled={applying}>
              全部接受
            </button>
            <button className="glacier-btn glacier-btn--outline" onClick={rejectAllHunks} type="button" disabled={applying}>
              全部拒绝
            </button>
            <button
              className="glacier-btn glacier-btn--primary"
              disabled={applying || !acceptedHunkIds.length}
              onClick={() => void handleApplyPartial()}
              type="button"
            >
              {applying
                ? "写入中…"
                : acceptedHunkIds.length === selectedScheme.hunks.length
                  ? "写入全部修改"
                  : `部分写入（${acceptedHunkIds.length} 处）`}
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}

function SchemeCard({
  scheme,
  active,
  onSelect
}: {
  scheme: ModificationScheme;
  active: boolean;
  onSelect: () => void;
}) {
  const hunkCount = scheme.hunks.length;
  return (
    <article className={`glacier-plan-card ${active ? "glacier-plan-card--active" : ""}`}>
      <div className="glacier-plan-head">
        <h3 className="glacier-plan-title">{scheme.title}</h3>
        <span className="glacier-plan-badge">{DIRECTION_LABELS[scheme.direction] ?? scheme.direction}</span>
      </div>
      <p className="glacier-plan-desc">{scheme.changes_summary || scheme.rationale}</p>
      <p className="glacier-plan-meta">
        {hunkCount ? `${hunkCount} 处脚本修改` : "策略说明（无具体 cell 修改）"}
      </p>
      <button
        className={`glacier-plan-btn ${active ? "glacier-plan-btn--active" : ""}`}
        onClick={onSelect}
        type="button"
      >
        {active ? "预览稿子" : "选中并预览"}
      </button>
    </article>
  );
}

function ScriptSchemePreview({
  previewTable,
  previewMode,
  summary,
  onPreviewModeChange
}: {
  previewTable: ReturnType<typeof buildPreviewTable>;
  previewMode: PreviewMode;
  summary: ReturnType<typeof schemeDecisionSummary> | null;
  onPreviewModeChange: (mode: PreviewMode) => void;
}) {
  return (
    <section className="glacier-script-preview">
      <div className="glacier-script-preview-head">
        <h4 className="glacier-scheme-detail-title">稿子预览</h4>
        <div className="glacier-preview-mode" role="tablist" aria-label="Preview mode">
          <button
            className={previewMode === "all_proposed" ? "active" : ""}
            onClick={() => onPreviewModeChange("all_proposed")}
            type="button"
          >
            方案全文
          </button>
          <button
            className={previewMode === "accepted_only" ? "active" : ""}
            onClick={() => onPreviewModeChange("accepted_only")}
            type="button"
            disabled={!summary?.accepted}
          >
            仅已接受
          </button>
        </div>
      </div>
      <p className="glacier-script-preview-note">
        下方为受影响分镜的预览（非节点图）。绿色为将写入的修改，灰色删除线为保留原文。
      </p>
      <div className="glacier-script-preview-table-wrap">
        <table className="glacier-script-preview-table">
          <thead>
            <tr>
              <th>#</th>
              {previewTable[0]?.cells.map((cell) => (
                <th key={cell.column.column_id}>{cell.column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {previewTable.map((row) => (
              <tr key={row.rowId}>
                <td className="glacier-preview-row-num">{row.rowOrder}</td>
                {row.cells.map((cell) => (
                  <td
                    className={[
                      "glacier-preview-cell",
                      cell.change === "accepted" ? "is-accepted" : "",
                      cell.change === "rejected" ? "is-rejected" : "",
                      cell.change === "pending" ? "is-pending" : "",
                      cell.change === "proposed" ? "is-proposed" : ""
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    key={cell.column.column_id}
                  >
                    {cell.change && cell.change !== "rejected" ? (
                      <span className="glacier-preview-value">{cell.value || "（空）"}</span>
                    ) : (
                      <span className="glacier-preview-value glacier-preview-value--unchanged">
                        {cell.value || "（空）"}
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SchemeDetail({
  scheme,
  script,
  hunkDecisions,
  onHunkDecision
}: {
  scheme: ModificationScheme;
  script: Script;
  hunkDecisions: Record<string, HunkDecision>;
  onHunkDecision: (hunkId: string, decision: HunkDecision) => void;
}) {
  const cells = listSchemePreviewCells(script, scheme, hunkDecisions);

  return (
    <section className="glacier-scheme-detail">
      <h4 className="glacier-scheme-detail-title">修改说明</h4>
      {scheme.rationale ? <p className="glacier-scheme-detail-text">{scheme.rationale}</p> : null}
      {scheme.sacrifice ? (
        <p className="glacier-scheme-detail-meta">
          <strong>牺牲点：</strong>
          {scheme.sacrifice}
        </p>
      ) : null}
      {scheme.response_script ? (
        <p className="glacier-scheme-detail-meta">
          <strong>回应话术：</strong>
          {scheme.response_script}
        </p>
      ) : null}

      {cells.length ? (
        <>
          <h5 className="glacier-hunk-list-title">逐条决定（接受 / 拒绝）</h5>
          <ul className="glacier-hunk-list">
            {cells.map((cell) => (
              <li
                className={[
                  "glacier-hunk-item",
                  cell.decision === true ? "is-accepted" : "",
                  cell.decision === false ? "is-rejected" : ""
                ]
                  .filter(Boolean)
                  .join(" ")}
                key={cell.hunkId}
              >
                <p className="glacier-hunk-context">
                  第 {cell.rowOrder} 镜 · {cell.columnLabel}
                </p>
                <div className="glacier-hunk-diff">
                  <del className="glacier-hunk-removed">{cell.removed || "（空）"}</del>
                  <span className="glacier-hunk-arrow" aria-hidden="true">
                    →
                  </span>
                  <ins className="glacier-hunk-added">{cell.added}</ins>
                </div>
                <div className="glacier-hunk-actions" role="group" aria-label="Hunk decision">
                  <button
                    className={`glacier-hunk-btn ${cell.decision === true ? "active accept" : ""}`}
                    onClick={() => onHunkDecision(cell.hunkId, true)}
                    type="button"
                  >
                    接受
                  </button>
                  <button
                    className={`glacier-hunk-btn ${cell.decision === false ? "active reject" : ""}`}
                    onClick={() => onHunkDecision(cell.hunkId, false)}
                    type="button"
                  >
                    拒绝
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="glacier-plans-placeholder">本方案仅含策略说明，无可写入脚本的 cell 修改。</p>
      )}
    </section>
  );
}
