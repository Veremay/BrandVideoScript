"use client";

import { useEffect, useState } from "react";

import { VIDEO_CATEGORY_OPTIONS } from "@/lib/videoCategories";
import type { VideoCategory } from "@/lib/types";

type CreateProjectDialogProps = {
  open: boolean;
  defaultTitle: string;
  creating: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (videoCategory: VideoCategory) => void;
};

export function CreateProjectDialog({
  open,
  defaultTitle,
  creating,
  error,
  onClose,
  onConfirm
}: CreateProjectDialogProps) {
  const [videoCategory, setVideoCategory] = useState<VideoCategory>("lifestyle");

  useEffect(() => {
    if (!open) return;
    setVideoCategory("lifestyle");
  }, [open]);

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !creating) onClose();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, creating, onClose]);

  if (!open) return null;

  return (
    <div className="persona-overlay" role="dialog" aria-modal="true" aria-labelledby="create-project-title">
      <button
        aria-label="Close"
        className="persona-overlay-backdrop"
        disabled={creating}
        onClick={onClose}
        type="button"
      />
      <section className="create-project-dialog">
        <header className="create-project-dialog-header">
          <p className="eyebrow">New Project</p>
          <h2 id="create-project-title">Video Category</h2>
          <p className="create-project-dialog-subtitle">
            Choose a category for <strong>{defaultTitle}</strong>. More categories will be added later.
          </p>
        </header>

        <div className="create-project-category-list" role="radiogroup" aria-label="Video Category">
          {VIDEO_CATEGORY_OPTIONS.map((option) => {
            const selected = videoCategory === option.value;
            return (
              <label
                className={`create-project-category-option${selected ? " is-selected" : ""}`}
                key={option.value}
              >
                <input
                  checked={selected}
                  name="video-category"
                  onChange={() => setVideoCategory(option.value)}
                  type="radio"
                  value={option.value}
                />
                <span className="create-project-category-copy">
                  <span className="create-project-category-label">{option.label}</span>
                  <span className="create-project-category-description">{option.description}</span>
                </span>
              </label>
            );
          })}
        </div>

        {error ? <p className="formError create-project-dialog-error">{error}</p> : null}

        <footer className="create-project-dialog-actions">
          <button className="create-project-dialog-cancel" disabled={creating} onClick={onClose} type="button">
            Cancel
          </button>
          <button
            className="create-project-dialog-submit"
            disabled={creating}
            onClick={() => onConfirm(videoCategory)}
            type="button"
          >
            {creating ? "Creating…" : "Create Project"}
          </button>
        </footer>
      </section>
    </div>
  );
}
