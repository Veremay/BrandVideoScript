import { normalizeProject } from "@/lib/normalizeProject";
import type {
  AppMode,
  BrandInsightCategory,
  BrandInsightConfidence,
  BrandInsightStatus,
  CoordinatorMessage,
  CoordinatorQuote,
  PlatformContext,
  Project,
  VideoCategory,
  RationaleEdge,
  RationaleNode,
  ModificationScheme,
  NegotiationPreparation,
  RequestedPerspective,
  Script,
  ScriptSnapshotReason,
  ScriptSnapshotSummary
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const REQUEST_TIMEOUT_MS = 120000;
const PROJECT_TIMEOUT_MS = 180000;
/** Brand + Expert (and optional repair) with 32B; backend allows ~300s per LLM call. */
const AGENT_PIPELINE_TIMEOUT_MS = 900000;
const BRIEF_PARSE_TIMEOUT_MS = AGENT_PIPELINE_TIMEOUT_MS;
const SCHEME_GENERATE_TIMEOUT_MS = AGENT_PIPELINE_TIMEOUT_MS;

function formatApiError(message: string, status: number): string {
  const fallback = message.trim() || `Request failed: ${status}`;
  try {
    const parsed = JSON.parse(message) as { detail?: unknown };
    const { detail } = parsed;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") {
            return item.msg;
          }
          return null;
        })
        .filter((part): part is string => Boolean(part));
      if (parts.length) return parts.join("; ");
    }
  } catch {
    // Non-JSON error body — use raw text.
  }
  return fallback;
}

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
      throw new Error(formatApiError(message, response.status));
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

export async function createProject(
  userId: string,
  title: string,
  videoCategory: VideoCategory = "lifestyle",
  mode: AppMode = "full"
): Promise<Project> {
  const project = await request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, title, video_category: videoCategory, mode })
  });
  return normalizeProject(project)!;
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

export async function syncMapFromScript(
  projectId: string,
  userId: string,
  changedRowIds: string[] = []
): Promise<Project> {
  let project: Project | null = null;
  await syncMapFromScriptStream(projectId, userId, changedRowIds, (event) => {
    if (event.type === "done") {
      project = event.project;
    }
    if (event.type === "error") {
      throw new Error(event.message);
    }
  });
  if (!project) throw new Error("Map update finished without returning a project.");
  return project;
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

type BriefParseStreamEvent =
  | { type: "status"; message: string }
  | { type: "heartbeat" }
  | { type: "done"; project: Project; parse_summary: Record<string, number> }
  | { type: "error"; message: string };

async function readSseStream<T>(
  response: Response,
  parseBlock: (block: string) => T | null,
  onEvent: (event: T) => void
): Promise<void> {
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
      const event = parseBlock(part.trim());
      if (event) onEvent(event);
    }
  }
  if (buffer.trim()) {
    const event = parseBlock(buffer.trim());
    if (event) onEvent(event);
  }
}

type BriefParseSseEvent =
  | { type: "status"; message: string }
  | { type: "heartbeat" }
  | { type: "done"; parse_summary: Record<string, number>; project?: Project }
  | { type: "error"; message: string };

function parseBriefSseBlock(block: string): BriefParseSseEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data = line.slice(5).trim();
  }
  if (!data) return null;
  const payload = JSON.parse(data) as Record<string, unknown>;
  if (event === "status") return { type: "status", message: String(payload.message ?? "") };
  if (event === "heartbeat") return { type: "heartbeat" };
  if (event === "done") {
    return {
      type: "done",
      parse_summary: (payload.parse_summary ?? {}) as Record<string, number>,
      project: payload.project ? normalizeProject(payload.project as Project) ?? undefined : undefined,
    };
  }
  if (event === "error") return { type: "error", message: String(payload.message ?? "Parse failed") };
  return null;
}

function briefParseSummaryFromProject(project: Project): Record<string, number> {
  const insights = project.brand_insights ?? [];
  return {
    explicit_requirements: insights.filter((i) => i.category === "explicit_requirement").length,
    implicit_requirements: insights.filter((i) => i.category === "implicit_requirement").length,
  };
}

async function waitForBriefParseResult(
  projectId: string,
  userId: string,
  baselineUpdatedAt: string | null | undefined,
  onStatus?: (message: string) => void
): Promise<{ project: Project; parse_summary: Record<string, number> }> {
  const started = Date.now();
  let delayMs = 1500;
  while (Date.now() - started < BRIEF_PARSE_TIMEOUT_MS) {
    const project = await fetchProject(projectId, userId);
    const status = project.brief?.parse_status;
    const finishedThisRun =
      status === "parsed" &&
      (!baselineUpdatedAt || project.updated_at !== baselineUpdatedAt);
    if (finishedThisRun) {
      return { project, parse_summary: briefParseSummaryFromProject(project) };
    }
    if (status === "failed" && (!baselineUpdatedAt || project.updated_at !== baselineUpdatedAt)) {
      throw new Error("Brief parse failed");
    }
    onStatus?.(status === "parsing" ? "Parsing… (reconnecting)" : "Waiting for parse…");
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    delayMs = Math.min(delayMs + 500, 4000);
  }
  throw new Error("Timed out waiting for brief parse");
}

export async function parseBriefStream(
  projectId: string,
  userId: string,
  onEvent: (event: BriefParseStreamEvent) => void
): Promise<void> {
  const baseline = await fetchProject(projectId, userId);
  const baselineUpdatedAt = baseline.updated_at;

  let embeddedProject: Project | undefined;
  let parseSummary: Record<string, number> = {};
  let sawError = false;
  let sawProgress = false;
  let streamError: unknown = null;

  try {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/brief/parse/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Parse failed: ${response.status}`);
    }
    await readSseStream(response, parseBriefSseBlock, (event) => {
      if (event.type === "status" || event.type === "heartbeat") {
        sawProgress = true;
        onEvent(event);
        return;
      }
      if (event.type === "error") {
        sawError = true;
        onEvent(event);
        return;
      }
      sawProgress = true;
      parseSummary = event.parse_summary ?? {};
      embeddedProject = event.project;
    });
  } catch (err) {
    streamError = err;
  }

  if (sawError) return;

  if (embeddedProject) {
    onEvent({ type: "done", project: embeddedProject, parse_summary: parseSummary });
    return;
  }

  // Stream often drops mid-parse (incomplete chunked encoding) while the backend
  // task keeps running. Poll until this run finishes (updated_at changes).
  if (streamError || sawProgress) {
    onEvent({ type: "status", message: "Parsing… (reconnecting)" });
    const recovered = await waitForBriefParseResult(
      projectId,
      userId,
      baselineUpdatedAt,
      (message) => onEvent({ type: "status", message })
    );
    onEvent({
      type: "done",
      project: recovered.project,
      parse_summary: Object.keys(parseSummary).length ? parseSummary : recovered.parse_summary,
    });
    return;
  }

  if (streamError instanceof Error) throw streamError;
  if (streamError) throw new Error(String(streamError));
  throw new Error("Parse stream ended unexpectedly");
}

type GraphSyncStreamEvent =
  | { type: "status"; message: string }
  | { type: "heartbeat" }
  | { type: "done"; project: Project }
  | { type: "error"; message: string };

function parseGraphSyncSseBlock(block: string): GraphSyncStreamEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data = line.slice(5).trim();
  }
  if (!data) return null;
  const payload = JSON.parse(data) as Record<string, unknown>;
  if (event === "status") return { type: "status", message: String(payload.message ?? "") };
  if (event === "heartbeat") return { type: "heartbeat" };
  if (event === "done") return { type: "done", project: normalizeProject(payload.project as Project)! };
  if (event === "error") return { type: "error", message: String(payload.message ?? "Map update failed") };
  return null;
}

export async function syncMapFromScriptStream(
  projectId: string,
  userId: string,
  changedRowIds: string[],
  onEvent: (event: GraphSyncStreamEvent) => void
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/graph/sync-from-script/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, changed_row_ids: changedRowIds }),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Map update failed: ${response.status}`);
  }
  await readSseStream(response, parseGraphSyncSseBlock, onEvent);
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
  return request(
    `/projects/${projectId}/persona/provision-from-analytics`,
    {
      method: "POST",
      body: JSON.stringify({ user_id: userId, ...payload })
    },
    payload.run_audience_parse ? AGENT_PIPELINE_TIMEOUT_MS : PROJECT_TIMEOUT_MS
  );
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
    brand_insights: Array<{
      insight_id: string;
      title: string;
      content: string;
      reason: string;
      confidence: BrandInsightConfidence;
      category: BrandInsightCategory;
      status: BrandInsightStatus;
      created_by?: "user" | "agent";
    }>;
  }
): Promise<Project> {
  const project = await request<Project>(`/projects/${projectId}/brand/requirements`, {
    method: "PATCH",
    body: JSON.stringify({
      user_id: userId,
      brand_insights: payload.brand_insights
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
    job?: string;
    explanation?: string;
    reason?: string;
    personal_experiences?: string[];
    characteristic_values?: Record<string, string>;
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
    job: string;
    explanation: string;
    reason: string;
    personal_experiences: string[];
    characteristic_values: Record<string, string>;
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

export async function updateVanillaSetupStage(
  projectId: string,
  userId: string,
  stage: "requirements" | "conflicts" | "complete",
  data?: Project["vanilla_setup_data"]
): Promise<Project> {
  return normalizeProject(
    await request(`/projects/${projectId}/vanilla-setup`, {
      method: "PATCH",
      body: JSON.stringify({ user_id: userId, stage, data })
    })
  )!;
}

export type CoordinatorStreamEvent =
  | { type: "token"; content: string }
  | {
      type: "artifact";
      rationale_nodes?: RationaleNode[];
      rationale_edges?: RationaleEdge[];
      related_node_ids?: string[];
      modification_schemes?: ModificationScheme[];
      new_scheme_ids?: string[];
    }
  | {
      type: "done";
      message_id: string;
      generated_artifact_ids?: string[];
      open_revision_proposals?: boolean;
      scheme_count?: number;
    }
  | { type: "error"; message: string; retryable?: boolean; project?: Project };

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
      related_node_ids: payload.related_node_ids as string[] | undefined,
      modification_schemes: payload.modification_schemes as ModificationScheme[] | undefined,
      new_scheme_ids: payload.new_scheme_ids as string[] | undefined
    };
  }
  if (event === "done") {
    return {
      type: "done",
      message_id: String(payload.message_id ?? ""),
      generated_artifact_ids: payload.generated_artifact_ids as string[] | undefined,
      open_revision_proposals: Boolean(payload.open_revision_proposals),
      scheme_count: typeof payload.scheme_count === "number" ? payload.scheme_count : undefined
    };
  }
  if (event === "error") {
    return {
      type: "error",
      message: String(payload.message ?? "Stream failed"),
      retryable: Boolean(payload.retryable),
      project: payload.project ? normalizeProject(payload.project as Project) ?? undefined : undefined
    };
  }
  return null;
}

export async function streamCoordinatorMessage(
  projectId: string,
  userId: string,
  payload: {
    message: string;
    task_type?: "user_message" | "quote_analysis" | "script_delta" | "generate_modification_schemes";
    requested_perspectives?: RequestedPerspective[];
    quotes?: CoordinatorQuote[];
    attachments?: Array<{ filename: string; content: string; mime_type: string; size: number }>;
    target_node_ids?: string[];
    changed_row_ids?: string[];
    mode?: "full" | "vanilla";
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
  await readSseStream(response, parseSseBlock, onEvent);
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

export async function batchUpdateGraphLayouts(
  projectId: string,
  userId: string,
  layouts: Record<string, { x: number; y: number }>,
  options?: { skipSnapshot?: boolean }
): Promise<Project> {
  const entries = Object.entries(layouts).map(([node_id, layout]) => ({ node_id, layout }));
  return normalizeProject(
    await request(`/projects/${projectId}/graph/layouts`, {
      method: "PATCH",
      body: JSON.stringify({
        user_id: userId,
        layouts: entries,
        skip_snapshot: options?.skipSnapshot ?? false
      })
    })
  )!;
}

export async function populateIssuePositions(
  projectId: string,
  userId: string,
  nodeId: string
): Promise<Project> {
  return normalizeProject(
    await request(
      `/projects/${projectId}/graph/nodes/${nodeId}/populate?user_id=${encodeURIComponent(userId)}`,
      { method: "POST" }
    )
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

export async function toggleGraphConsiderationQueue(
  projectId: string,
  userId: string,
  nodeId: string,
  inQueue: boolean
): Promise<Project> {
  return normalizeProject(
    await request(`/projects/${projectId}/graph/nodes/${nodeId}/consideration-queue`, {
      method: "PATCH",
      body: JSON.stringify({ user_id: userId, in_queue: inQueue })
    })
  )!;
}

export async function fetchModificationSchemes(projectId: string, userId: string): Promise<ModificationScheme[]> {
  const data = await request<{ schemes: ModificationScheme[] }>(
    `/projects/${projectId}/modification-schemes?user_id=${encodeURIComponent(userId)}`
  );
  return data.schemes;
}

export async function generateModificationSchemes(
  projectId: string,
  userId: string,
  options?: { target_issue_ids?: string[]; target_position_ids?: string[]; message?: string }
): Promise<{ project: Project; schemes: ModificationScheme[]; assistant_reply: string }> {
  const data = await request<{
    project: Project;
    schemes: ModificationScheme[];
    assistant_reply: string;
  }>(
    `/projects/${projectId}/modification-schemes/generate`,
    {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        target_issue_ids: options?.target_issue_ids ?? [],
        target_position_ids: options?.target_position_ids ?? [],
        message: options?.message ?? null
      })
    },
    SCHEME_GENERATE_TIMEOUT_MS
  );
  return { ...data, project: normalizeProject(data.project)! };
}

export async function applyModificationSchemeHunks(
  projectId: string,
  userId: string,
  schemeId: string,
  acceptedHunkIds: string[],
  rejectedHunkIds: string[] = []
): Promise<Project> {
  const data = await request<{ project: Project }>(
    `/projects/${projectId}/modification-schemes/${schemeId}/apply`,
    {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        accepted_hunk_ids: acceptedHunkIds,
        rejected_hunk_ids: rejectedHunkIds
      })
    },
    PROJECT_TIMEOUT_MS
  );
  return normalizeProject(data.project)!;
}

export async function toggleCommunicationSupport(
  projectId: string,
  userId: string,
  rowId: string,
  columnId: string,
  inList: boolean
): Promise<Project> {
  return normalizeProject(
    await request(`/projects/${projectId}/communication-support`, {
      method: "PATCH",
      body: JSON.stringify({ user_id: userId, row_id: rowId, column_id: columnId, in_list: inList })
    })
  )!;
}

export async function fetchVanillaArguePrompt(
  projectId: string,
  userId: string,
  rowId: string,
  columnId: string
): Promise<{ prompt: string; appendBlock: string }> {
  const data = await request<{ prompt: string; append_block: string }>(
    `/projects/${projectId}/vanilla/argue-prompt`,
    {
      method: "POST",
      body: JSON.stringify({ user_id: userId, row_id: rowId, column_id: columnId })
    }
  );
  return { prompt: data.prompt, appendBlock: data.append_block };
}

export async function generateNegotiationPlan(
  projectId: string,
  userId: string,
  message?: string
): Promise<{ project: Project; negotiation_preparation: NegotiationPreparation | null; assistant_reply: string }> {
  const data = await request<{
    project: Project;
    negotiation_preparation: NegotiationPreparation | null;
    assistant_reply: string;
  }>(
    `/projects/${projectId}/negotiation/generate`,
    {
      method: "POST",
      body: JSON.stringify({ user_id: userId, message: message ?? null })
    },
    SCHEME_GENERATE_TIMEOUT_MS
  );
  return { ...data, project: normalizeProject(data.project)! };
}

export async function createShareLink(
  projectId: string,
  userId: string
): Promise<{ share_token: string; expires_at: string | null }> {
  return request(`/projects/${projectId}/share`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId })
  });
}

export async function fetchShareScript(
  shareToken: string
): Promise<{ title: string; script: Script; expires_at: string | null }> {
  return request(`/share/${encodeURIComponent(shareToken)}`);
}

export async function saveShareFeedback(
  shareToken: string,
  rowId: string,
  columnId: string,
  value: string
): Promise<{ script: Script }> {
  return request(`/share/${encodeURIComponent(shareToken)}/feedback`, {
    method: "PATCH",
    body: JSON.stringify({ row_id: rowId, column_id: columnId, value })
  });
}
