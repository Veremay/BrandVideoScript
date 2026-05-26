"use client";

import { useState } from "react";

import { createProject, fetchProject, fetchProjects } from "@/lib/api";
import { useAppStore } from "@/store/appStore";

export function ProjectList() {
  const { projects, setProject, setProjects, userId } = useAppStore();
  const [creating, setCreating] = useState(false);
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
        {projects.map((project) => (
          <button className="projectCard" key={project._id} onClick={() => handleOpen(project._id)} type="button">
            <strong>{project.title}</strong>
            <span>{new Date(project.updated_at).toLocaleString()}</span>
          </button>
        ))}
        {projects.length === 0 ? <p className="emptyState">No projects yet. Create one to get started.</p> : null}
      </section>
    </main>
  );
}
