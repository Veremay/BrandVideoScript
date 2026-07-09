"use client";

import { useEffect, useState } from "react";

import { VIDEO_CATEGORY_OPTIONS } from "@/lib/videoCategories";
import type { AppMode, VideoCategory } from "@/lib/types";

export type CreateProjectPayload = {
  title: string;
  videoCategory: VideoCategory;
  mode: AppMode;
};

type CreateProjectDialogProps = {
  open: boolean;
  defaultTitle: string;
  creating: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (payload: CreateProjectPayload) => void;
};

export function CreateProjectDialog({
  open,
  defaultTitle,
  creating,
  error,
  onClose,
  onConfirm
}: CreateProjectDialogProps) {
  const [title, setTitle] = useState(defaultTitle);
  const [videoCategory, setVideoCategory] = useState<VideoCategory>("lifestyle");
  const [mode, setMode] = useState<AppMode>("full");

  useEffect(() => {
    if (!open) return;
    setTitle(defaultTitle);
    setVideoCategory("lifestyle");
    setMode("full");
  }, [open, defaultTitle]);

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !creating) onClose();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, creating, onClose]);

  const trimmedTitle = title.trim();
  const canSubmit = trimmedTitle.length > 0 && !creating;

  if (!open) return null;

  return (
    <div className="hub-overlay" role="dialog" aria-modal="true" aria-labelledby="create-project-title">
      <button
        aria-label="Close"
        className="hub-overlay-backdrop"
        disabled={creating}
        onClick={onClose}
        type="button"
      />
      <section className="hub-dialog app-scrollbar">
        <header className="hub-dialog-header">
          <p className="hub-eyebrow">New Project</p>
          <h2 className="hub-headline hub-headline-sm" id="create-project-title">
            Create Project
          </h2>
          <p className="hub-lead">Name your project and choose a video category.</p>
        </header>

        <div className="hub-field">
          <label className="hub-label" htmlFor="project-title">
            Project name
          </label>
          <input
            autoFocus
            className="hub-input"
            id="project-title"
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Brand Script 1"
            value={title}
          />
        </div>

        <div className="hub-field">
          <span className="hub-label">Video Category</span>
          <div className="hub-category-list" role="radiogroup" aria-label="Video Category">
            {VIDEO_CATEGORY_OPTIONS.map((option) => {
              const selected = videoCategory === option.value;
              return (
                <label className={`hub-category-option${selected ? " is-selected" : ""}`} key={option.value}>
                  <input
                    checked={selected}
                    name="video-category"
                    onChange={() => setVideoCategory(option.value)}
                    type="radio"
                    value={option.value}
                  />
                  <span className="hub-category-copy">
                    <span className="hub-category-label">{option.label}</span>
                    <span className="hub-category-description">{option.description}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </div>

        <div className="hub-field">
          <span className="hub-label">Script Setting</span>
          <div className="hub-category-list" role="radiogroup" aria-label="Script Setting">
            <label className={`hub-category-option${mode === "full" ? " is-selected" : ""}`}>
              <input
                checked={mode === "full"}
                name="project-mode"
                onChange={() => setMode("full")}
                type="radio"
                value="full"
              />
              <span className="hub-category-copy">
                <span className="hub-category-label">Setting 1</span>
                <span className="hub-category-description">Recommended setup for this script.</span>
              </span>
            </label>
            <label className={`hub-category-option${mode === "vanilla" ? " is-selected" : ""}`}>
              <input
                checked={mode === "vanilla"}
                name="project-mode"
                onChange={() => setMode("vanilla")}
                type="radio"
                value="vanilla"
              />
              <span className="hub-category-copy">
                <span className="hub-category-label">Setting 2</span>
                <span className="hub-category-description">Alternative setup for this script.</span>
              </span>
            </label>
          </div>
        </div>

        {error ? <p className="formError">{error}</p> : null}

        <footer className="hub-dialog-actions">
          <button className="figma-nav-btn figma-nav-outline" disabled={creating} onClick={onClose} type="button">
            Cancel
          </button>
          <button
            className="figma-nav-btn figma-nav-primary"
            disabled={!canSubmit}
            onClick={() => onConfirm({ title: trimmedTitle, videoCategory, mode })}
            type="button"
          >
            {creating ? "Creating…" : "Create Project"}
          </button>
        </footer>
      </section>
    </div>
  );
}
