import type {
  AgentMessage,
  AgentStreamPayload,
  AgentType,
  AudienceAnalysis,
  BrandInsightCategory,
  BrandInsightConfidence,
  BrandInsightStatus,
  PersonaAdSensitivity,
  Project,
  Script
} from "@/lib/types";

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

export type PersonaInput = {
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
};

export async function createPersona(projectId: string, userId: string, payload: PersonaInput): Promise<Project> {
  return request(`/projects/${projectId}/personas`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, ...payload })
  });
}

export async function updatePersona(
  projectId: string,
  userId: string,
  personaId: string,
  payload: Partial<PersonaInput>
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

export async function fetchAgentMessages(projectId: string, userId: string, agentType: AgentType): Promise<AgentMessage[]> {
  const data = await request<{ messages: AgentMessage[] }>(
    `/projects/${projectId}/agents/${agentType}/messages?user_id=${encodeURIComponent(userId)}`
  );
  return data.messages;
}

export type BrandInsightProposalItem = {
  category: BrandInsightCategory;
  title: string;
  content: string;
  reason?: string;
  confidence?: BrandInsightConfidence;
  evidence?: Array<{ source_type?: string; quote?: string }>;
};

export type BrandInsightProposalsArtifact = {
  type: "brand_insight_proposals";
  items: BrandInsightProposalItem[];
  persisted_count?: number;
  trace_run_id?: string;
};

export type AudienceAnalysisArtifact = {
  type: "audience_analysis";
  analysis: AudienceAnalysis;
  persona_id?: string | null;
  persona_name?: string | null;
  persisted?: boolean;
  trace_run_id?: string;
};

export type AgentStreamArtifact = BrandInsightProposalsArtifact | AudienceAnalysisArtifact;

export type AgentStreamDoneInfo = {
  messageId: string;
  proposalCount: number;
  persistedCount: number;
  analysisPersisted: boolean;
};

type StreamHandlers = {
  onToken: (content: string) => void;
  onDone: (info: AgentStreamDoneInfo) => void;
  onError: (message: string) => void;
  onArtifact?: (artifact: AgentStreamArtifact) => void;
};

export async function streamAgentMessage(
  projectId: string,
  agentType: AgentType,
  payload: AgentStreamPayload,
  handlers: StreamHandlers
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/agents/${agentType}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok || !response.body) {
    handlers.onError(await response.text());
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const event = frame.match(/^event: (.+)$/m)?.[1];
      const data = frame.match(/^data: (.+)$/m)?.[1];
      if (!event || !data) continue;

      const parsed = JSON.parse(data);
      if (event === "token") handlers.onToken(parsed.content ?? "");
      if (event === "artifact") {
        if (parsed.type === "audience_analysis") {
          handlers.onArtifact?.({
            type: "audience_analysis",
            analysis: parsed.analysis ?? ({} as AudienceAnalysis),
            persona_id: parsed.persona_id,
            persona_name: parsed.persona_name,
            persisted: parsed.persisted,
            trace_run_id: parsed.trace_run_id
          });
        } else {
          handlers.onArtifact?.({
            type: "brand_insight_proposals",
            items: parsed.items ?? [],
            persisted_count: parsed.persisted_count,
            trace_run_id: parsed.trace_run_id
          });
        }
      }
      if (event === "done") {
        handlers.onDone({
          messageId: parsed.message_id ?? "",
          proposalCount: parsed.proposal_count ?? 0,
          persistedCount: parsed.persisted_count ?? 0,
          analysisPersisted: parsed.analysis_persisted ?? false
        });
      }
      if (event === "error") handlers.onError(parsed.message ?? "Agent stream failed");
    }
  }
}
