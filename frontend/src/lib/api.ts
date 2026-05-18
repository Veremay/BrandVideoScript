import type { Project, Script } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function enterUser(userId: string): Promise<{ user_id: string; created_at: string }> {
  return request("/users/enter", {
    method: "POST",
    body: JSON.stringify({ user_id: userId })
  });
}

export async function fetchProjects(userId: string): Promise<Project[]> {
  const data = await request<{ projects: Project[] }>(`/projects?user_id=${encodeURIComponent(userId)}`);
  return data.projects;
}

export async function createProject(userId: string, title: string): Promise<Project> {
  return request("/projects", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, title })
  });
}

export async function fetchProject(projectId: string, userId: string): Promise<Project> {
  return request(`/projects/${projectId}?user_id=${encodeURIComponent(userId)}`);
}

export async function saveScript(projectId: string, userId: string, script: Script): Promise<Project> {
  return request(`/projects/${projectId}/script`, {
    method: "PATCH",
    body: JSON.stringify({ user_id: userId, script })
  });
}

