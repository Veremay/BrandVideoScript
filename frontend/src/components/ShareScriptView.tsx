"use client";

import { useEffect, useRef, useState } from "react";

import { ScriptGrid } from "@/components/ScriptGrid";
import { fetchShareScript, saveShareFeedback } from "@/lib/api";
import type { SaveStatus, Script } from "@/lib/types";

const SAVE_DELAY_MS = 700;

function savePillLabel(status: SaveStatus) {
  if (status === "editing") return "Editing";
  if (status === "saving") return "Saving";
  if (status === "failed") return "Failed";
  return "Saved";
}

export function ShareScriptView({ token }: { token: string }) {
  const [title, setTitle] = useState("");
  const [script, setScript] = useState<Script | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("saved");
  const pendingSave = useRef<{ rowId: string; columnId: string; value: string } | null>(null);
  const saveTimer = useRef<number | null>(null);
  const editRevision = useRef(0);

  useEffect(() => {
    if (!token) {
      setError("Invalid share link");
      setLoading(false);
      return;
    }

    fetchShareScript(token)
      .then((data) => {
        setTitle(data.title);
        setScript(data.script);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    return () => {
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
    };
  }, []);

  function handleUpdateCell(rowId: string, columnId: string, value: string) {
    editRevision.current += 1;
    setScript((current) => {
      if (!current) return current;
      return {
        ...current,
        rows: current.rows.map((row) =>
          row.row_id !== rowId
            ? row
            : {
                ...row,
                cells: row.cells.map((cell) => (cell.column_id === columnId ? { ...cell, value } : cell))
              }
        )
      };
    });
    setSaveStatus("editing");
    pendingSave.current = { rowId, columnId, value };

    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      const pending = pendingSave.current;
      if (!pending) return;
      const savingRevision = editRevision.current;

      setSaveStatus("saving");
      saveShareFeedback(token, pending.rowId, pending.columnId, pending.value)
        .then((result) => {
          // Ignore an older response when the reviewer continued typing while
          // the request was in flight. The later edit owns the next save timer.
          if (editRevision.current !== savingRevision) return;
          setScript(result.script);
          pendingSave.current = null;
          setSaveStatus("saved");
        })
        .catch(() => {
          if (editRevision.current === savingRevision) setSaveStatus("failed");
        });
    }, SAVE_DELAY_MS);
  }

  if (loading) {
    return (
      <main className="share-page">
        <p className="share-page-loading">Loading script…</p>
      </main>
    );
  }

  if (error || !script) {
    return (
      <main className="share-page">
        <p className="share-page-error">{error ?? "Share link not found or expired."}</p>
      </main>
    );
  }

  return (
    <main className="share-page">
      <header className="share-page-header">
        <div className="share-page-header-copy">
          <p className="share-page-eyebrow">Brand review</p>
          <h1 className="share-page-title">{title}</h1>
          <p className="share-page-hint">Review the script below and fill in the Brand Feedback column. Changes save automatically.</p>
        </div>
        <div className={`figma-save-pill status-${saveStatus === "editing" || saveStatus === "saving" ? "editing" : saveStatus === "failed" ? "failed" : "saved"}`}>
          {savePillLabel(saveStatus)}
        </div>
      </header>
      <section className="share-page-body">
        <ScriptGrid mode="share" onUpdateCell={handleUpdateCell} script={script} />
      </section>
    </main>
  );
}
