"use client";

import { useCallback, useEffect, useState } from "react";

import { createScriptSnapshot, fetchScriptSnapshots, restoreScriptSnapshot } from "@/lib/api";
import type { ScriptSnapshotSummary } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

const REASON_LABELS: Record<string, string> = {
  manual_save: "Manual save",
  auto_save: "Auto save",
  before_map_update: "Before map update",
  before_expert_apply: "Before applying scheme",
  after_expert_apply: "After applying scheme",
  brand_feedback_sync: "Brand feedback sync",
  import: "Import",
  rollback: "Rollback"
};

type ScriptSnapshotsPanelProps = {
  open: boolean;
  onClose: () => void;
};

export function ScriptSnapshotsPanel({ open, onClose }: ScriptSnapshotsPanelProps) {
  const { project, setProject } = useAppStore();
  const [snapshots, setSnapshots] = useState<ScriptSnapshotSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSnapshots = useCallback(async () => {
    if (!project) return;
    setLoading(true);
    setError(null);
    try {
      setSnapshots(await fetchScriptSnapshots(project._id, project.user_id));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load versions");
    } finally {
      setLoading(false);
    }
  }, [project]);

  useEffect(() => {
    if (!open || !project) return;
    void loadSnapshots();
  }, [open, project, loadSnapshots]);

  async function handleSaveSnapshot() {
    if (!project) return;
    setBusyId("__create__");
    setError(null);
    try {
      const created = await createScriptSnapshot(project._id, project.user_id, "manual_save");
      setProject({
        ...project,
        current_script_version_id: created.script_version_id,
        updated_at: created.created_at
      });
      await loadSnapshots();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save version");
    } finally {
      setBusyId(null);
    }
  }

  async function handleRestore(snapshotId: string) {
    if (!project) return;

    setBusyId(snapshotId);
    setError(null);
    try {
      const restored = await restoreScriptSnapshot(project._id, project.user_id, snapshotId);
      setProject(restored);
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Failed to restore version");
    } finally {
      setBusyId(null);
    }
  }

  if (!open || !project) return null;

  return (
    <div className="script-snapshots-drawer" role="complementary" aria-label="Script version history">
      <aside className="script-snapshots-panel">
        <button className="persona-panel-close" onClick={onClose} type="button" aria-label="Close">
          <IconClose />
        </button>
        <header className="persona-panel-header script-snapshots-header">
          <div className="persona-panel-heading">
            <div className="script-snapshots-title-row">
              <h2 className="persona-panel-title">Version History</h2>
              <button
                className="figma-nav-btn figma-nav-outline"
                disabled={busyId === "__create__"}
                onClick={() => void handleSaveSnapshot()}
                type="button"
              >
                {busyId === "__create__" ? "Saving…" : "Save Current Version"}
              </button>
            </div>
            <p className="persona-panel-subtitle">Save snapshots or restore a previous script state.</p>
          </div>
        </header>

        <div className="persona-panel-body script-snapshots-body">
          {error ? <p className="script-snapshots-error">{error}</p> : null}
          {loading ? <p className="script-snapshots-empty">Loading…</p> : null}
          {!loading && !snapshots.length ? (
            <p className="script-snapshots-empty">No saved versions yet. Edit the script, then save a snapshot.</p>
          ) : null}
          <ul className="script-snapshots-list">
            {snapshots.map((snapshot) => {
              const isCurrent = Boolean(
                snapshot.script_version_id &&
                  project.current_script_version_id &&
                  snapshot.script_version_id === project.current_script_version_id
              );
              return (
                <li className="script-snapshots-item" key={snapshot.snapshot_id}>
                  <button
                    aria-current={isCurrent ? "true" : undefined}
                    className={`script-snapshots-option ${isCurrent ? "active" : ""}`}
                    disabled={busyId !== null || isCurrent}
                    onClick={() => void handleRestore(snapshot.snapshot_id)}
                    type="button"
                  >
                    <span className="script-snapshots-meta">
                      <span className="script-snapshots-reason">{REASON_LABELS[snapshot.reason] ?? snapshot.reason}</span>
                      <time className="script-snapshots-time" dateTime={snapshot.created_at}>
                        {formatSnapshotTime(snapshot.created_at)}
                      </time>
                    </span>
                    <span className="script-snapshots-state">
                      {isCurrent ? "Current" : busyId === snapshot.snapshot_id ? "Switching…" : "Switch"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>
    </div>
  );
}

function formatSnapshotTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="18" x2="6" y1="6" y2="18" />
      <line x1="6" x2="18" y1="6" y2="18" />
    </svg>
  );
}
