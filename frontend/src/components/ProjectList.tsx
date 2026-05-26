"use client";

import { useState } from "react";

import { createProject, deleteProject, fetchProject, fetchProjects } from "@/lib/api";
import { useAppStore } from "@/store/appStore";

export function ProjectList() {
  const { projects, setProject, setProjects, userId } = useAppStore();
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!userId) return;

    setCreating(true);
    setError(null);
    try {
      const project = await createProject(userId, `Brand Script ${projects.length + 1}`);
      const nextProjects = await fetchProjects(userId);
      setProjects(nextProjects);
      setProject(project);
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
    <main className="projectsPage">
      <header className="projectsHeader">
        <div>
          <p className="eyebrow">Project Hub</p>
          <h1>Projects</h1>
        </div>
        <button onClick={handleCreate} disabled={creating} type="button">
          {creating ? "Creating…" : "New Project"}
        </button>
      </header>
      {error ? <p className="formError">{error}</p> : null}
      <section className="projectGrid">
        {projects.map((project) => {
          const isDeleting = deletingId === project._id;
          return (
            <article className="projectCardWrap" key={project._id}>
              <button
                className="projectCard"
                disabled={isDeleting}
                onClick={() => handleOpen(project._id)}
                type="button"
              >
                <strong>{project.title}</strong>
                <span>{new Date(project.updated_at).toLocaleString()}</span>
              </button>
              <button
                aria-label={`Delete ${project.title}`}
                className="projectCardDelete"
                disabled={isDeleting}
                onClick={(event) => handleDelete(event, project._id, project.title)}
                type="button"
              >
                <IconTrash />
              </button>
            </article>
          );
        })}
        {projects.length === 0 ? <p className="emptyState">No projects yet. Create one to get started.</p> : null}
      </section>
    </main>
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
