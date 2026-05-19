"use client";

import { useEffect, useMemo, useState } from "react";

import { EditorShell } from "@/components/EditorShell";
import { ProjectList } from "@/components/ProjectList";
import { UserGate } from "@/components/UserGate";
import { enterUser, fetchProjects } from "@/lib/api";
import { useAppStore } from "@/store/appStore";

export default function Home() {
  const { userId, project, setProjects, setUserId } = useAppStore();
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
      .then((projects) => {
        setUserId(storedUserId);
        setProjects(projects);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [setProjects, setUserId]);

  const content = useMemo(() => {
    if (loading) {
      return <main className="centerStage">正在连接工作区...</main>;
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
      {error ? <div className="errorBanner">{error}</div> : null}
      {content}
    </>
  );
}
