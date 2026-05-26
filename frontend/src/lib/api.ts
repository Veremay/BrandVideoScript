import type {
  BrandInsightCategory,
  BrandInsightConfidence,
  BrandInsightStatus,
  PersonaAdSensitivity,
  Project,
  Script,
  ScriptSnapshotReason,
  ScriptSnapshotSummary
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const REQUEST_TIMEOUT_MS = 15000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
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
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Backend request timed out. Make sure the API is running at http://localhost:8000.");
    }
    if (error instanceof TypeError) {
      throw new Error("Cannot reach backend. Make sure the API is running at http://localhost:8000.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
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

export async function fetchScriptSnapshots(projectId: string, userId: string): Promise<ScriptSnapshotSummary[]> {
  const data = await request<{ snapshots: ScriptSnapshotSummary[] }>(
    `/projects/${projectId}/script/snapshots?user_id=${encodeURIComponent(userId)}`
  );
  return data.snapshots;
}

export async function createScriptSnapshot(
  projectId: string,
  userId: string,
  reason: ScriptSnapshotReason = "manual_save"
): Promise<ScriptSnapshotSummary> {
  const data = await request<{ snapshot: ScriptSnapshotSummary }>(`/projects/${projectId}/script/snapshots`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, reason })
  });
  return data.snapshot;
}

export async function restoreScriptSnapshot(projectId: string, userId: string, snapshotId: string): Promise<Project> {
  return request(
    `/projects/${projectId}/script/snapshots/${snapshotId}/restore?user_id=${encodeURIComponent(userId)}`,
    { method: "POST" }
  );
}

export async function saveBrief(projectId: string, userId: string, text: string, filename?: string): Promise<Project> {
  return request(`/projects/${projectId}/brief`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, text, filename })
  });
}

export async function createBrandInsight(
  projectId: string,
  userId: string,
  payload: {
    category: BrandInsightCategory;
    title: string;
    content: string;
    reason?: string;
    evidence?: Array<Record<string, unknown>>;
    confidence?: BrandInsightConfidence;
    status?: BrandInsightStatus;
  }
): Promise<Project> {
  return request(`/projects/${projectId}/agents/brand/insights`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, ...payload })
  });
}

export async function updateBrandInsight(
  projectId: string,
  userId: string,
  insightId: string,
  payload: Partial<{
    category: BrandInsightCategory;
    title: string;
    content: string;
    reason: string;
    evidence: Array<Record<string, unknown>>;
    confidence: BrandInsightConfidence;
    status: BrandInsightStatus;
  }>
): Promise<Project> {
  return request(`/projects/${projectId}/agents/brand/insights/${insightId}`, {
    method: "PATCH",
    body: JSON.stringify({ user_id: userId, ...payload })
  });
}

export async function deleteBrandInsight(projectId: string, userId: string, insightId: string): Promise<Project> {
  return request(`/projects/${projectId}/agents/brand/insights/${insightId}?user_id=${encodeURIComponent(userId)}`, {
    method: "DELETE"
  });
}

export async function saveScriptCell(
  projectId: string,
  userId: string,
  rowId: string,
  columnId: string,
  value: string
): Promise<Project> {
  return request(`/projects/${projectId}/script/cells`, {
    method: "PATCH",
    body: JSON.stringify({ user_id: userId, row_id: rowId, column_id: columnId, value })
  });
}

export async function createScriptRow(projectId: string, userId: string, afterRowId?: string): Promise<Project> {
  return request(`/projects/${projectId}/script/rows`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, after_row_id: afterRowId })
  });
}

export async function deleteScriptRow(projectId: string, userId: string, rowId: string): Promise<Project> {
  return request(`/projects/${projectId}/script/rows/${rowId}?user_id=${encodeURIComponent(userId)}`, {
    method: "DELETE"
  });
}

export async function createScriptColumn(
  projectId: string,
  userId: string,
  afterColumnId: string | undefined,
  label: string,
  multiline: boolean
): Promise<Project> {
  return request(`/projects/${projectId}/script/columns`, {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      after_column_id: afterColumnId,
      label,
      type: multiline ? "textarea" : "text",
      multiline
    })
  });
}

export async function renameScriptColumn(projectId: string, userId: string, columnId: string, label: string): Promise<Project> {
  return request(`/projects/${projectId}/script/columns/${columnId}`, {
    method: "PATCH",
    body: JSON.stringify({ user_id: userId, label })
  });
}

export async function deleteScriptColumn(projectId: string, userId: string, columnId: string): Promise<Project> {
  return request(`/projects/${projectId}/script/columns/${columnId}?user_id=${encodeURIComponent(userId)}`, {
    method: "DELETE"
  });
}

export async function createPersona(
  projectId: string,
  userId: string,
  payload: {
    name: string;
    icon?: string;
    gender?: string;
    age_range?: string;
    preferences?: string;
    behavior?: string;
    platform_context?: string;
    ad_sensitivity?: PersonaAdSensitivity;
    trust_trigger?: string[];
    reject_trigger?: string[];
  }
): Promise<Project> {
  return request(`/projects/${projectId}/personas`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, ...payload })
  });
}

export async function updatePersona(
  projectId: string,
  userId: string,
  personaId: string,
  payload: Partial<{
    name: string;
    gender: string;
    age_range: string;
    preferences: string;
    behavior: string;
    platform_context: string;
    ad_sensitivity: PersonaAdSensitivity;
    trust_trigger: string[];
    reject_trigger: string[];
  }>
): Promise<Project> {
  return request(`/projects/${projectId}/personas/${personaId}`, {
    method: "PATCH",
    body: JSON.stringify({ user_id: userId, ...payload })
  });
}

export async function deletePersona(projectId: string, userId: string, personaId: string): Promise<Project> {
  return request(`/projects/${projectId}/personas/${personaId}?user_id=${encodeURIComponent(userId)}`, {
    method: "DELETE"
  });
}

export async function setActivePersona(projectId: string, userId: string, personaId: string | null): Promise<Project> {
  return request(`/projects/${projectId}/active-persona`, {
    method: "PATCH",
    body: JSON.stringify({ user_id: userId, persona_id: personaId })
  });
}
