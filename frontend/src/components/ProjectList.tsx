"use client";

import { useState } from "react";

import { createProject, fetchProject, fetchProjects } from "@/lib/api";
import { useAppStore } from "@/store/appStore";

export function ProjectList() {
  const { projects, setProject, setProjects, userId } = useAppStore();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!userId) {
      return;
    }

    setCreating(true);
    setError(null);
    try {
      const project = await createProject(userId, `品牌脚本 ${projects.length + 1}`);
      const nextProjects = await fetchProjects(userId);
      setProjects(nextProjects);
      setProject(project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建项目失败");
    } finally {
      setCreating(false);
    }
  }

  async function handleOpen(projectId: string) {
    if (!userId) {
      return;
    }

    setError(null);
    try {
      setProject(await fetchProject(projectId, userId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "打开项目失败");
    }
  }

  return (
    <main className="projectsPage">
      <header className="projectsHeader">
        <div>
          <p className="eyebrow">Project Hub</p>
          <h1>项目列表</h1>
        </div>
        <button onClick={handleCreate} disabled={creating}>
          {creating ? "创建中..." : "新建项目"}
        </button>
      </header>
      {error ? <p className="formError">{error}</p> : null}
      <section className="projectGrid">
        {projects.map((project) => (
          <button className="projectCard" key={project._id} onClick={() => handleOpen(project._id)}>
            <strong>{project.title}</strong>
            <span>{new Date(project.updated_at).toLocaleString()}</span>
          </button>
        ))}
        {projects.length === 0 ? <p className="emptyState">还没有项目，先创建一个。</p> : null}
      </section>
    </main>
  );
}

