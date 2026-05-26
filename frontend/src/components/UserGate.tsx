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
    <main className="gate">
      <form className="gatePanel" onSubmit={handleSubmit}>
        <p className="eyebrow">BrandVideo MVP</p>
        <h1>Enter Workspace</h1>
        <label htmlFor="user-id">User ID</label>
        <input
          id="user-id"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="e.g. creator_may"
        />
        {error ? <p className="formError">{error}</p> : null}
        <button type="submit" disabled={submitting || !value.trim()}>
          {submitting ? "Entering…" : "Enter"}
        </button>
      </form>
    </main>
  );
}
