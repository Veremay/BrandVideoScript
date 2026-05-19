"use client";

import { FormEvent, useState } from "react";

import { enterUser, fetchProjects } from "@/lib/api";
import { useAppStore } from "@/store/appStore";

export function UserGate() {
  const { setProjects, setUserId } = useAppStore();
  const [value, setValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const userId = value.trim();
    if (!userId) return;

    setSubmitting(true);
    setError(null);
    try {
      await enterUser(userId);
      const projects = await fetchProjects(userId);
      window.localStorage.setItem("brandvideo:user_id", userId);
      setUserId(userId);
      setProjects(projects);
    } catch (err) {
      setError(err instanceof Error ? err.message : "进入失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="gate">
      <form className="gatePanel" onSubmit={handleSubmit}>
        <p className="eyebrow">BrandVideo MVP</p>
        <h1>进入脚本工作台</h1>
        <label htmlFor="user-id">自定义 user_id</label>
        <input
          id="user-id"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="例如 creator_may"
        />
        {error ? <p className="formError">{error}</p> : null}
        <button type="submit" disabled={submitting || !value.trim()}>
          {submitting ? "进入中..." : "进入"}
        </button>
      </form>
    </main>
  );
}
