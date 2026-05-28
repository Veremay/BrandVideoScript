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
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="app-hub hub-page hub-page--centered">
      <div className="hub-gate">
        <p className="hub-brand-mark">BrandVideo</p>
        <form className="hub-glass-pane" onSubmit={handleSubmit}>
          <div>
            <p className="hub-eyebrow">Workspace</p>
            <h1 className="hub-headline hub-headline-sm">Enter Workspace</h1>
            <p className="hub-lead">Sign in with your creator ID to open projects and scripts.</p>
          </div>
          <div className="hub-field">
            <label className="hub-label" htmlFor="user-id">
              User ID
            </label>
            <input
              autoComplete="username"
              className="hub-input"
              id="user-id"
              onChange={(event) => setValue(event.target.value)}
              placeholder="e.g. creator_may"
              value={value}
            />
          </div>
          {error ? <p className="formError">{error}</p> : null}
          <button
            className="figma-nav-btn figma-nav-primary hub-btn-block"
            disabled={submitting || !value.trim()}
            type="submit"
          >
            {submitting ? "Entering…" : "Enter"}
          </button>
        </form>
      </div>
    </main>
  );
}
