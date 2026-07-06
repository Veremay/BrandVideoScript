"use client";

import { useEffect, useMemo, useState } from "react";

import { EditorShell } from "@/components/EditorShell";
import { ProjectList } from "@/components/ProjectList";
import { ProjectSetup } from "@/components/ProjectSetup";
import { UserGate } from "@/components/UserGate";
import { enterUser, fetchProject, fetchProjects } from "@/lib/api";
import { getProjectSetupStatus } from "@/lib/projectSetup";
import { useAppStore } from "@/store/appStore";

const STORAGE_PROJECT_ID = "brandvideo:project_id";

export default function Home() {
  const { userId, project, setProject, setProjects, setUserId } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [setupProjectId, setSetupProjectId] = useState<string | null>(null);

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

  useEffect(() => {
    if (!project) {
      setSetupProjectId(null);
      return;
    }

    if (!getProjectSetupStatus(project).complete) {
      setSetupProjectId(project._id);
    }
  }, [project]);

  function handleSetupBack() {
    window.localStorage.removeItem(STORAGE_PROJECT_ID);
    setProject(null);
    setSetupProjectId(null);
  }

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

    if (setupProjectId === project._id) {
      return (
        <ProjectSetup
          onBack={handleSetupBack}
          onEnterEditor={() => setSetupProjectId(null)}
        />
      );
    }

    return <EditorShell />;
  }, [loading, project, setupProjectId, userId]);

  return (
    <>
      {error ? <div className="hub-error-banner">{error}</div> : null}
      {content}
    </>
  );
}
