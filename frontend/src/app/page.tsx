"use client";

import { useEffect, useMemo, useState } from "react";

import { EditorShell } from "@/components/EditorShell";
import { ProjectList } from "@/components/ProjectList";
import { UserGate } from "@/components/UserGate";
import { enterUser, fetchProject, fetchProjects } from "@/lib/api";
import { useAppStore } from "@/store/appStore";

const STORAGE_PROJECT_ID = "brandvideo:project_id";

export default function Home() {
  const { userId, project, setProject, setProjects, setUserId } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const storedUserId = window.localStorage.getItem("brandvideo:user_id");
    if (!storedUserId) {
      setLoading(false);
      return;
    }

    enterUser(storedUserId)
      .then(() => fetchProjects(storedUserId))
      .then(async (projects) => {
        setUserId(storedUserId);
        setProjects(projects);
        const storedProjectId = window.localStorage.getItem(STORAGE_PROJECT_ID);
        if (!storedProjectId) return;
        try {
          setProject(await fetchProject(storedProjectId, storedUserId));
        } catch {
          window.localStorage.removeItem(STORAGE_PROJECT_ID);
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [setProject, setProjects, setUserId]);

  const content = useMemo(() => {
    if (loading) {
      return (
        <main className="app-hub hub-page hub-page--centered">
          <p className="hub-loading">Connecting to workspace…</p>
        </main>
      );
    }

    if (!userId) {
      return <UserGate />;
    }

    if (!project) {
      return <ProjectList />;
    }

    return <EditorShell />;
  }, [loading, project, userId]);

  return (
    <>
      {error ? <div className="hub-error-banner">{error}</div> : null}
      {content}
    </>
  );
}
