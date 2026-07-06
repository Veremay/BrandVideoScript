"use client";

import { useState } from "react";

import { CreateProjectDialog, type CreateProjectPayload } from "@/components/CreateProjectDialog";
import { createProject, deleteProject, fetchProject, fetchProjects } from "@/lib/api";
import { VIDEO_CATEGORY_OPTIONS } from "@/lib/videoCategories";
import { useAppStore } from "@/store/appStore";

function categoryLabel(value: string | undefined) {
  return VIDEO_CATEGORY_OPTIONS.find((option) => option.value === value)?.label ?? "Lifestyle";
}

export function ProjectList() {
  const { projects, setProject, setProjects, userId } = useAppStore();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const nextProjectTitle = `Brand Script ${projects.length + 1}`;

  async function handleCreateConfirm({ title, videoCategory, mode }: CreateProjectPayload) {
    if (!userId) return;

    setCreating(true);
    setError(null);
    try {
      const project = await createProject(userId, title, videoCategory, mode);
      const nextProjects = await fetchProjects(userId);
      setProjects(nextProjects);
      window.localStorage.setItem("brandvideo:project_id", project._id);
      setProject(project);
      setCreateDialogOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  async function handleOpen(projectId: string) {
    if (!userId) return;

    setError(null);
    try {
      window.localStorage.setItem("brandvideo:project_id", projectId);
      setProject(await fetchProject(projectId, userId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open project");
    }
  }

  async function handleDelete(event: React.MouseEvent, projectId: string, title: string) {
    event.stopPropagation();
    if (!userId || deletingId) return;

    const confirmed = window.confirm(`Delete "${title}"? This cannot be undone.`);
    if (!confirmed) return;

    setDeletingId(projectId);
    setError(null);
    try {
      await deleteProject(projectId, userId);
      const nextProjects = await fetchProjects(userId);
      setProjects(nextProjects);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <main className="app-hub hub-page">
      <div className="hub-shell">
        <header className="hub-header">
          <div className="hub-header-copy">
            <p className="hub-eyebrow">Project Hub</p>
            <h1 className="hub-headline">Projects</h1>
            <p className="hub-lead">Pick up a script or start a new brand video project.</p>
          </div>
          <button
            className="figma-nav-btn figma-nav-primary"
            disabled={creating}
            onClick={() => setCreateDialogOpen(true)}
            type="button"
          >
            <IconPlus />
            New Project
          </button>
        </header>

        {error && !createDialogOpen ? <p className="formError">{error}</p> : null}

        <CreateProjectDialog
          creating={creating}
          defaultTitle={nextProjectTitle}
          error={createDialogOpen ? error : null}
          onClose={() => {
            if (creating) return;
            setCreateDialogOpen(false);
            setError(null);
          }}
          onConfirm={(payload) => void handleCreateConfirm(payload)}
          open={createDialogOpen}
        />

        <section className="hub-project-grid">
          {projects.map((project) => {
            const isDeleting = deletingId === project._id;
            return (
              <article className="hub-project-card" key={project._id}>
                <button
                  className="hub-project-card-open"
                  disabled={isDeleting}
                  onClick={() => handleOpen(project._id)}
                  type="button"
                >
                  <span className="hub-project-card-chip">
                    {categoryLabel(project.video_category)} · {project.mode === "vanilla" ? "Setting 2" : "Setting 1"}
                  </span>
                  <strong className="hub-project-card-title">{project.title}</strong>
                  <span className="hub-project-card-meta">
                    Updated {new Date(project.updated_at).toLocaleString()}
                  </span>
                </button>
                <button
                  aria-label={`Delete ${project.title}`}
                  className="hub-project-card-delete"
                  disabled={isDeleting}
                  onClick={(event) => handleDelete(event, project._id, project.title)}
                  type="button"
                >
                  <IconTrash />
                </button>
              </article>
            );
          })}
          {projects.length === 0 ? (
            <p className="hub-empty">No projects yet. Create one to get started.</p>
          ) : null}
        </section>
      </div>
    </main>
  );
}

function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="12" x2="12" y1="5" y2="19" />
      <line x1="5" x2="19" y1="12" y2="12" />
    </svg>
  );
}

function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14H6L5 6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M9 6V4h6v2" />
    </svg>
  );
}
