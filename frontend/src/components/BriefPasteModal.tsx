"use client";

import { useState } from "react";

type BriefPasteModalProps = {
  open: boolean;
  onClose: () => void;
  onSave: (text: string) => Promise<void>;
};

export function BriefPasteModal({ open, onClose, onSave }: BriefPasteModalProps) {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  async function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed) {
      window.alert("请先粘贴 Brief 内容。");
      return;
    }

    setSaving(true);
    try {
      await onSave(trimmed);
      setText("");
      onClose();
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "保存 Brief 失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <button className="brief-modal-backdrop" onClick={onClose} type="button" aria-label="关闭 Brief 粘贴" />
      <div className="brief-modal" role="dialog" aria-labelledby="brief-modal-title" aria-modal="true">
        <header className="brief-modal-header">
          <h2 id="brief-modal-title">粘贴 Brief</h2>
          <button className="brief-modal-close" onClick={onClose} type="button" aria-label="关闭">
            ×
          </button>
        </header>
        <p className="brief-modal-hint">MVP 支持纯文本粘贴；也可通过 Topbar 上传 .md / .txt 文件。</p>
        <textarea
          className="brief-modal-textarea"
          placeholder="在此粘贴 Brief 正文…"
          rows={12}
          value={text}
          onChange={(event) => setText(event.target.value)}
          disabled={saving}
        />
        <footer className="brief-modal-actions">
          <button className="figma-nav-btn figma-nav-outline" onClick={onClose} type="button" disabled={saving}>
            取消
          </button>
          <button className="figma-nav-btn figma-nav-primary" onClick={handleSubmit} type="button" disabled={saving}>
            {saving ? "保存中…" : "保存 Brief"}
          </button>
        </footer>
      </div>
    </>
  );
}
