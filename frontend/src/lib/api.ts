import { normalizeProject } from "@/lib/normalizeProject";
import type {
  BrandInsightCategory,
  BrandInsightConfidence,
  BrandInsightStatus,
  BrandRequirement,
  CoordinatorMessage,
  CoordinatorQuote,
  PersonaAdSensitivity,
  PlatformContext,
  Project,
  RationaleEdge,
  RationaleNode,
  RequestedPerspective,
  Script,
  ScriptSnapshotReason,
  ScriptSnapshotSummary
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const REQUEST_TIMEOUT_MS = 15000;
const PROJECT_TIMEOUT_MS = 60000;
/** Brief parse runs Brand + Expert agents sequentially; each LLM call can take ~60s. */
const BRIEF_PARSE_TIMEOUT_MS = 180000;

async function request<T>(path: string, init?: RequestInit, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

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
      const seconds = Math.round(timeoutMs / 1000);
      throw new Error(
        `Request timed out after ${seconds}s. If you just uploaded a brief, parsing can take 1–2 minutes — wait and retry, or check the backend terminal for progress.`
      );
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

export async function deleteProject(projectId: string, userId: string): Promise<void> {
  await request(`/projects/${projectId}?user_id=${encodeURIComponent(userId)}`, {
    method: "DELETE"
  });
}

export async function fetchProject(projectId: string, userId: string): Promise<Project> {
  const project = await request<Project>(
    `/projects/${projectId}?user_id=${encodeURIComponent(userId)}`,
    undefined,
    PROJECT_TIMEOUT_MS
  );
  return normalizeProject(project)!;
}

export async function fetchProjectGraph(
  projectId: string,
  userId: string
): Promise<{ rationale_nodes: RationaleNode[]; rationale_edges: RationaleEdge[]; updated_at: string }> {
  return request(`/projects/${projectId}/graph?user_id=${encodeURIComponent(userId)}`, undefined, PROJECT_TIMEOUT_MS);
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

export async function parseBrief(
  projectId: string,
  userId: string
): Promise<{ project: Project; parse_summary: Record<string, number> }> {
  const data = await request<{ project: Project; parse_summary: Record<string, number> }>(
    `/projects/${projectId}/brief/parse`,
    {
      method: "POST",
      body: JSON.stringify({ user_id: userId })
    },
    BRIEF_PARSE_TIMEOUT_MS
  );
  return { ...data, project: normalizeProject(data.project)! };
}

export async function provisionPersonasFromAnalytics(
  projectId: string,
  userId: string,
  payload: {
    platform_context?: PlatformContext;
    content_category?: string;
    brand_name?: string;
    video_topic?: string;
    run_audience_parse?: boolean;
  } = {}
): Promise<{
  personas: Project["personas"];
  active_persona_id: string | null;
  project: Project;
  analytics_meta?: Record<string, unknown>;
}> {
  return request(`/projects/${projectId}/persona/provision-from-analytics`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, ...payload })
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

export async function updateBrandRequirements(
  projectId: string,
  userId: string,
  payload: {
    explicit_requirements: BrandRequirement[];
    implicit_requirements: BrandRequirement[];
  }
): Promise<Project> {
  const project = await request<Project>(`/projects/${projectId}/brand/requirements`, {
    method: "PATCH",
    body: JSON.stringify({
      user_id: userId,
      explicit_requirements: payload.explicit_requirements,
      implicit_requirements: payload.implicit_requirements
    })
  });
  return normalizeProject(project)!;
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

export async function fetchCoordinatorMessages(
  projectId: string,
  userId: string,
  limit = 50
): Promise<CoordinatorMessage[]> {
  const data = await request<{ messages: CoordinatorMessage[] }>(
    `/projects/${projectId}/coordinator/messages?user_id=${encodeURIComponent(userId)}&limit=${limit}`
  );
  return data.messages;
}

export type CoordinatorStreamEvent =
  | { type: "token"; content: string }
  | { type: "artifact"; rationale_nodes?: RationaleNode[]; rationale_edges?: RationaleEdge[]; related_node_ids?: string[] }
  | { type: "done"; message_id: string; generated_artifact_ids?: string[] }
  | { type: "error"; message: string };

function parseSseBlock(block: string): CoordinatorStreamEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data = line.slice(5).trim();
  }
  if (!data) return null;
  const payload = JSON.parse(data) as Record<string, unknown>;
  if (event === "token") return { type: "token", content: String(payload.content ?? "") };
  if (event === "artifact") {
    return {
      type: "artifact",
      rationale_nodes: payload.rationale_nodes as RationaleNode[] | undefined,
      rationale_edges: payload.rationale_edges as RationaleEdge[] | undefined,
      related_node_ids: payload.related_node_ids as string[] | undefined
    };
  }
  if (event === "done") {
    return {
      type: "done",
      message_id: String(payload.message_id ?? ""),
      generated_artifact_ids: payload.generated_artifact_ids as string[] | undefined
    };
  }
  if (event === "error") return { type: "error", message: String(payload.message ?? "Stream failed") };
  return null;
}

export async function streamCoordinatorMessage(
  projectId: string,
  userId: string,
  payload: {
    message: string;
    task_type?: "user_message" | "quote_analysis" | "script_delta";
    requested_perspectives?: RequestedPerspective[];
    quotes?: CoordinatorQuote[];
    target_node_ids?: string[];
    changed_row_ids?: string[];
  },
  onEvent: (event: CoordinatorStreamEvent) => void
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/coordinator/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, ...payload })
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Stream failed: ${response.status}`);
  }
  if (!response.body) throw new Error("Stream body missing");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const event = parseSseBlock(part.trim());
      if (event) onEvent(event);
    }
  }
  if (buffer.trim()) {
    const event = parseSseBlock(buffer.trim());
    if (event) onEvent(event);
  }
}

export async function createGraphNode(
  projectId: string,
  userId: string,
  payload: {
    node_type?: "issue" | "position" | "argument" | "reference";
    title: string;
    content: string;
    source_type?: RationaleNode["source_type"];
    layout?: { x: number; y: number };
    linked_script_refs?: Array<{ row_id: string; column_id?: string; text_snapshot?: string }>;
  }
): Promise<Project> {
  return normalizeProject(
    await request(`/projects/${projectId}/graph/nodes`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId, ...payload })
    })
  )!;
}

export async function updateGraphNode(
  projectId: string,
  userId: string,
  nodeId: string,
  payload: Partial<{ title: string; content: string; status: string; layout: { x: number; y: number } }>
): Promise<Project> {
  return normalizeProject(
    await request(`/projects/${projectId}/graph/nodes/${nodeId}`, {
      method: "PATCH",
      body: JSON.stringify({ user_id: userId, ...payload })
    })
  )!;
}

export async function deleteGraphNode(projectId: string, userId: string, nodeId: string): Promise<Project> {
  return normalizeProject(
    await request(`/projects/${projectId}/graph/nodes/${nodeId}?user_id=${encodeURIComponent(userId)}`, {
      method: "DELETE"
    })
  )!;
}

export async function createGraphEdge(
  projectId: string,
  userId: string,
  fromNodeId: string,
  toNodeId: string,
  relationType = "responds_to"
): Promise<Project> {
  return normalizeProject(
    await request(`/projects/${projectId}/graph/edges`, {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        from_node_id: fromNodeId,
        to_node_id: toNodeId,
        relation_type: relationType
      })
    })
  )!;
}

export async function deleteGraphEdge(projectId: string, userId: string, edgeId: string): Promise<Project> {
  return normalizeProject(
    await request(`/projects/${projectId}/graph/edges/${edgeId}?user_id=${encodeURIComponent(userId)}`, {
      method: "DELETE"
    })
  )!;
}

export async function toggleGraphNegotiationQueue(
  projectId: string,
  userId: string,
  nodeId: string,
  inQueue: boolean
): Promise<Project> {
  return normalizeProject(
    await request(`/projects/${projectId}/graph/nodes/${nodeId}/negotiation-queue`, {
      method: "PATCH",
      body: JSON.stringify({ user_id: userId, in_queue: inQueue })
    })
  )!;
}
