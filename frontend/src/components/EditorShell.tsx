"use client";

import { useEffect, useRef, useState } from "react";

import { ScriptGrid } from "@/components/ScriptGrid";
import {
  applyExpertSuggestion,
  createBrandInsight,
  createPersona,
  deleteBrandInsight,
  deletePersona,
  fetchAgentMessages,
  fetchProject,
  listScriptSnapshots,
  restoreScriptSnapshot,
  saveBrief,
  saveScript,
  setActivePersona,
  streamAgentMessage,
  updateBrandInsight,
  updateExpertSuggestionStatus,
  updatePersona,
  type PersonaInput
} from "@/lib/api";
import type {
  AgentMessage,
  AgentQuote,
  AgentType,
  AudienceAnalysis,
  BrandInsight,
  BrandInsightCategory,
  BrandInsightConfidence,
  BrandInsightStatus,
  ExpertDirection,
  ExpertHunk,
  ExpertSuggestion,
  Persona,
  PersonaAdSensitivity,
  Project,
  Script,
  ScriptSnapshotSummary
} from "@/lib/types";
import { useAppStore } from "@/store/appStore";

const SAVE_DELAY_MS = 700;

type AgentTone = "brand" | "audience" | "expert";

const AGENTS: Array<{ type: AgentType; title: string; tone: AgentTone }> = [
  { type: "brand", title: "品牌方 Agent", tone: "brand" },
  { type: "audience", title: "观众 Agent", tone: "audience" },
  { type: "expert", title: "专家 Agent", tone: "expert" }
];

type AgentBadge = { label: string; badgeClass: string };

function brandAgentBadge(project: Project): AgentBadge {
  const st = project.brand_research?.status;
  if (st === "running") return { label: "Brief 分析中", badgeClass: "badge-wait" };
  if (st === "failed") return { label: "Brief 分析失败", badgeClass: "badge-new" };
  if (st === "done") return { label: "分析完成", badgeClass: "badge-done" };
  return { label: "待 Brief", badgeClass: "badge-wait" };
}

function audienceAgentBadge(project: Project): AgentBadge {
  if (!project.personas.length) return { label: "新建 persona", badgeClass: "badge-wait" };
  if (!project.active_persona_id) return { label: "未选 persona", badgeClass: "badge-wait" };
  if (project.stale.audience) return { label: "分析过期", badgeClass: "badge-new" };
  if (project.audience_analysis?.updated_at) return { label: "分析已更新", badgeClass: "badge-done" };
  return { label: "待分析", badgeClass: "badge-wait" };
}

function expertAgentBadge(project: Project): AgentBadge {
  if (project.stale.expert) return { label: "有新输入", badgeClass: "badge-new" };
  return { label: "已同步", badgeClass: "badge-done" };
}

function getAgentBadge(agent: AgentType, project: Project): AgentBadge {
  if (agent === "brand") return brandAgentBadge(project);
  if (agent === "audience") return audienceAgentBadge(project);
  return expertAgentBadge(project);
}

const BRAND_TABS: Array<{ category: BrandInsightCategory; label: string; addLabel: string }> = [
  { category: "explicit_requirement", label: "显式需求", addLabel: "添加需求" },
  { category: "implicit_requirement", label: "隐式需求", addLabel: "添加洞察" },
  { category: "brand_feedback", label: "品牌反馈", addLabel: "添加反馈" }
];

export function EditorShell() {
  const {
    editor,
    layout,
    project,
    script,
    expert,
    setAgentColumnWidth,
    setBrandPinnedTab,
    setProject,
    setSaveStatus,
    setUserId,
    openPanel,
    openDiffOverlay,
    setSnapshotsOpen,
    setExpertApplyToast
  } = useAppStore();
  const hasHydrated = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activePanel = layout.activePanel ?? "brand";

  useEffect(() => {
    if (!project || !script) return;

    if (!hasHydrated.current) {
      hasHydrated.current = true;
      return;
    }

    if (editor.saveStatus !== "editing") return;

    const timeoutId = window.setTimeout(async () => {
      setSaveStatus("saving");
      try {
        const savedProject = await saveScript(project._id, project.user_id, script);
        setProject(savedProject);
        setSaveStatus("saved");
      } catch {
        setSaveStatus("failed");
      }
    }, SAVE_DELAY_MS);

    return () => window.clearTimeout(timeoutId);
  }, [editor.saveStatus, project, script, setProject, setSaveStatus]);

  useEffect(() => {
    if (!project) return;
    if (project.brand_research?.status !== "running") return;
    const id = window.setInterval(async () => {
      try {
        const p = await fetchProject(project._id, project.user_id);
        setProject(p);
      } catch {
        /* ignore transient errors while polling */
      }
    }, 2000);
    return () => window.clearInterval(id);
  }, [project?._id, project?.brand_research?.status, project?.user_id, setProject]);

  function handleBack() {
    setProject(null);
  }

  function handleLogout() {
    window.localStorage.removeItem("brandvideo:user_id");
    setUserId(undefined);
    setProject(null);
  }

  function handleSplitterPointerDown(event: React.PointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startWidth = layout.agentsColWidth;

    function handleMove(moveEvent: PointerEvent) {
      setAgentColumnWidth(startWidth - (moveEvent.clientX - startX));
    }

    function handleUp() {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
  }

  async function persistBrief(text: string, filename?: string) {
    if (!project) return;
    const savedProject = await saveBrief(project._id, project.user_id, text, filename);
    setProject(savedProject);
    setBrandPinnedTab("explicit_requirement");
    openPanel("brand");
  }

  async function handleBriefFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const isSupported = file.name.endsWith(".md") || file.name.endsWith(".txt");
    if (!isSupported) {
      window.alert("当前 MVP 仅支持 .md / .txt Brief。");
      return;
    }

    await persistBrief(await file.text(), file.name);
  }

  if (!project || !script) return null;

  return (
    <main className="app" style={{ "--agents-col-width": `${layout.agentsColWidth}px` } as React.CSSProperties}>
      <header className="topbar">
        <button className="topbar-btn" onClick={handleBack} type="button">
          <IconBack />
          项目
        </button>
        <span className="logo">Creator Studio</span>
        <input ref={fileInputRef} accept=".md,.txt,text/markdown,text/plain" hidden onChange={handleBriefFile} type="file" />
        <button className="topbar-btn" onClick={() => fileInputRef.current?.click()} type="button">
          <IconUpload />
          上传 Brief
        </button>
        <span className="topbar-brief-hint">
          {project.brief.filename ?? "MD / TXT"}
          {project.brand_research?.status === "running" ? " · 品牌分析中…" : null}
          {project.brand_research?.status === "failed" ? " · 品牌分析失败" : null}
          {project.brand_research?.status === "done" ? " · 品牌分析完成" : null}
        </span>
        <div className="topbar-sep" />
        <input className="topbar-project-input" value={project.title} readOnly aria-label="项目名称" />
        <div className="topbar-spacer" />
        <button
          className="topbar-btn"
          onClick={() => {
            const candidate = pickLatestPreviewableSuggestion(project);
            if (!candidate) {
              setExpertApplyToast({ tone: "warning", message: "暂无可预览的专家方案，请先让专家 Agent 生成方案。" });
              window.setTimeout(() => setExpertApplyToast(undefined), 4000);
              return;
            }
            openPanel("expert");
            openDiffOverlay(candidate.suggestion_id);
          }}
          type="button"
        >
          <IconEye />
          预览修改稿
        </button>
        <button className="topbar-btn" onClick={() => setSnapshotsOpen(true)} type="button">
          <IconHistory />
          版本
        </button>
        <div className={`status-pill status-${statusClass(editor.saveStatus)}`}>● {statusLabel(editor.saveStatus)}</div>
        <button className="topbar-btn" onClick={handleLogout} type="button">
          退出
        </button>
      </header>

      <section className="editor-col">
        <div className="editor-toolbar">
          <span className="editor-toolbar-label">脚本编辑器</span>
          <div className="editor-toolbar-spacer" />
          <button className="tool-btn" type="button">
            <IconEdit />
            格式化
          </button>
          <button className="tool-btn" type="button">
            <IconCheck />
            字数统计
          </button>
        </div>
        <ScriptGrid script={script} />
      </section>

      <div
        className="col-splitter"
        onPointerDown={handleSplitterPointerDown}
        role="separator"
        aria-orientation="vertical"
        aria-label="拖动调整脚本编辑器与 Agent 面板宽度"
      />

      <aside className="agents-col">
        {AGENTS.map((agent) => {
          const badge = getAgentBadge(agent.type, project);
          return (
            <section
              className={`agent-panel panel-${agent.tone} ${activePanel === agent.type ? "expanded" : "collapsed"}`}
              key={agent.type}
            >
              <button className="panel-header" onClick={() => openPanel(agent.type)} type="button">
                <span className={`panel-dot dot-${agent.tone}`} />
                <span className={`panel-name name-${agent.tone}`}>{agent.title}</span>
                <span className={`panel-badge ${badge.badgeClass}`}>{badge.label}</span>
                <IconChevron />
              </button>
              {activePanel === agent.type ? <AgentBody agent={agent.type} selectedText={editor.selectedText} /> : null}
            </section>
          );
        })}
      </aside>
      <PersonaModalContainer />
      <DiffOverlayContainer />
      <SnapshotsDrawer />
      {expert.lastApplyToast ? (
        <div className={`apply-toast apply-toast-${expert.lastApplyToast.tone}`} role="status">
          {expert.lastApplyToast.message}
        </div>
      ) : null}
    </main>
  );
}

function pickLatestPreviewableSuggestion(project: Project): ExpertSuggestion | null {
  const drafts = project.expert_suggestions.filter((item) => item.status === "draft" || item.status === "partially_applied");
  if (drafts.length === 0) return null;
  return [...drafts].sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))[0];
}

function AgentBody({ agent, selectedText }: { agent: AgentType; selectedText?: string }) {
  const { brand, project, setBrandPinnedTab, setProject } = useAppStore();

  if (agent === "brand" && project) {
    const activeTab = brand.activePinnedTab;
    const activeTabMeta = BRAND_TABS.find((tab) => tab.category === activeTab) ?? BRAND_TABS[0];
    const insights = project.brand_insights.filter((insight) => insight.category === activeTab);

    async function handleAddInsight() {
      if (!project) return;
      const savedProject = await createBrandInsight(project._id, project.user_id, {
        category: activeTab,
        title: activeTabMeta.label,
        content: "新的品牌洞察",
        reason: project.brief.summary ? `来自 Brief：${project.brief.summary}` : "用户手动新增。",
        evidence: project.brief.text ? [{ source_type: "brief", quote: project.brief.summary || project.brief.text.slice(0, 120) }] : [],
        confidence: "medium",
        status: "new"
      });
      setProject(savedProject);
    }

    return (
      <div className="panel-body">
        <div className="pinned">
          <div className="pinned-tabs">
            {BRAND_TABS.map((tab) => (
              <button
                className={`ptab ${activeTab === tab.category ? "active-brand" : ""}`}
                key={tab.category}
                onClick={() => setBrandPinnedTab(tab.category)}
                type="button"
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="pinned-content show">
            {project.brief.summary ? <div className="brief-summary">Brief: {project.brief.summary}</div> : null}
            {project.brand_research?.status === "failed" && project.brand_research.error_message ? (
              <div className="brief-summary" role="alert">
                品牌分析失败：{project.brand_research.error_message}
              </div>
            ) : null}
            <div className="pinned-list">
              {insights.length ? (
                insights.map((insight, index) => <PinnedItem insight={insight} key={insight.insight_id} mark={String(index + 1).padStart(2, "0")} />)
              ) : (
                <div className="pinned-empty">暂无条目</div>
              )}
            </div>
            <div className="pinned-add-row">
              <button className="pinned-add-btn" onClick={handleAddInsight} type="button">
                + {activeTabMeta.addLabel}
              </button>
            </div>
          </div>
        </div>
        <AgentChat agent="brand" selectedText={selectedText} placeholder="向品牌方 Agent 提问或粘贴 PR feedback..." />
      </div>
    );
  }

  if (agent === "audience" && project) {
    return <AudiencePanel project={project} selectedText={selectedText} />;
  }

  if (agent === "expert" && project) {
    return <ExpertPanel project={project} selectedText={selectedText} />;
  }

  return null;
}

function PinnedItem({ insight, mark }: { insight: BrandInsight; mark: string }) {
  const { project, setProject } = useAppStore();
  const [expanded, setExpanded] = useState(false);
  const [draft, setDraft] = useState({
    title: insight.title,
    content: insight.content,
    reason: insight.reason,
    confidence: insight.confidence,
    status: insight.status
  });

  useEffect(() => {
    setDraft({
      title: insight.title,
      content: insight.content,
      reason: insight.reason,
      confidence: insight.confidence,
      status: insight.status
    });
  }, [insight]);

  if (!project) return null;

  async function handleSave() {
    if (!project) return;
    const savedProject = await updateBrandInsight(project._id, project.user_id, insight.insight_id, draft);
    setProject(savedProject);
  }

  async function handleDelete() {
    if (!project) return;
    const savedProject = await deleteBrandInsight(project._id, project.user_id, insight.insight_id);
    setProject(savedProject);
  }

  return (
    <div className={`pinned-item ${expanded ? "is-expanded" : ""}`}>
      <button className="pinned-item-main" onClick={() => setExpanded((value) => !value)} type="button">
        <span className="pinned-item-mark mark-blue">{mark}</span>
        <span className="pinned-item-text">{insight.content}</span>
        <span className={`insight-chip confidence-${insight.confidence}`}>{confidenceLabel(insight.confidence)}</span>
        <span className={`insight-chip status-${insight.status}`}>{statusLabelInsight(insight.status)}</span>
      </button>
      {expanded ? (
        <div className="insight-details">
          <label>
            标题
            <input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
          </label>
          <label>
            内容
            <textarea value={draft.content} onChange={(event) => setDraft({ ...draft, content: event.target.value })} />
          </label>
          <label>
            Reason
            <textarea value={draft.reason} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} />
          </label>
          <div className="insight-select-row">
            <label>
              Confidence
              <select
                value={draft.confidence}
                onChange={(event) => setDraft({ ...draft, confidence: event.target.value as BrandInsightConfidence })}
              >
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </label>
            <label>
              Status
              <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value as BrandInsightStatus })}>
                <option value="new">New</option>
                <option value="confirmed">Confirmed</option>
                <option value="pending">Pending</option>
                <option value="ignored">Ignored</option>
              </select>
            </label>
          </div>
          <div className="insight-evidence">
            <span>Evidence</span>
            {insight.evidence.length ? (
              insight.evidence.map((item, index) => <blockquote key={`${insight.insight_id}-${index}`}>{item.quote ?? "未填写 quote"}</blockquote>)
            ) : (
              <p>暂无 evidence</p>
            )}
          </div>
          <div className="insight-actions">
            <button className="pinned-add-btn" onClick={handleSave} type="button">保存</button>
            <button className="insight-delete-btn" onClick={handleDelete} type="button">删除</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function AgentChat({ agent, selectedText, placeholder }: { agent: AgentType; selectedText?: string; placeholder: string }) {
  const {
    agentChats,
    appendAgentMessage,
    appendAssistantToken,
    project,
    setAgentError,
    setAgentMessages,
    setAgentStreaming,
    setBrandPinnedTab,
    setProject,
    startAssistantMessage
  } = useAppStore();
  const [message, setMessage] = useState("");
  const chat = agentChats[agent];

  useEffect(() => {
    if (!project) return;

    fetchAgentMessages(project._id, project.user_id, agent)
      .then((messages) => setAgentMessages(agent, messages))
      .catch((error) => setAgentError(agent, String(error)));
  }, [agent, project, setAgentError, setAgentMessages]);

  async function handleSend() {
    const content = message.trim();
    if (!project || !content || chat.streaming) return;

    const quotes: AgentQuote[] = selectedText ? [{ text: selectedText }] : [];
    const timestamp = Date.now();
    const userMessage: AgentMessage = {
      _id: `local_user_${timestamp}`,
      project_id: project._id,
      user_id: project.user_id,
      agent_type: agent,
      role: "user",
      content,
      quotes,
      created_at: new Date().toISOString()
    };
    const assistantId = `local_assistant_${timestamp}`;
    const assistantMessage: AgentMessage = {
      _id: assistantId,
      project_id: project._id,
      user_id: project.user_id,
      agent_type: agent,
      role: "assistant",
      content: "",
      quotes: [],
      created_at: new Date().toISOString()
    };

    appendAgentMessage(agent, userMessage);
    startAssistantMessage(agent, assistantMessage);
    setAgentStreaming(agent, true);
    setAgentError(agent, undefined);
    setMessage("");

    let shouldRefresh = false;
    try {
      await streamAgentMessage(
        project._id,
        agent,
        { user_id: project.user_id, content, quotes },
        {
          onToken: (token) => appendAssistantToken(agent, assistantId, token),
          onArtifact: (artifact) => {
            if (artifact.type === "brand_insight_proposals" && (artifact.persisted_count ?? 0) > 0) {
              setBrandPinnedTab("explicit_requirement");
              shouldRefresh = true;
            }
            if (artifact.type === "audience_analysis" && artifact.persisted) {
              shouldRefresh = true;
            }
            if (artifact.type === "expert_suggestions" && (artifact.persisted_count ?? 0) > 0) {
              shouldRefresh = true;
            }
          },
          onDone: async ({ persistedCount, analysisPersisted, suggestionsPersistedCount }) => {
            setAgentStreaming(agent, false);
            const needsRefresh =
              shouldRefresh || persistedCount > 0 || analysisPersisted || suggestionsPersistedCount > 0;
            const [messages, refreshed] = await Promise.all([
              fetchAgentMessages(project._id, project.user_id, agent),
              needsRefresh ? fetchProject(project._id, project.user_id) : Promise.resolve(null)
            ]);
            setAgentMessages(agent, messages);
            if (refreshed) setProject(refreshed);
          },
          onError: (error) => {
            setAgentStreaming(agent, false);
            setAgentError(agent, error);
          }
        }
      );
    } catch (error) {
      setAgentStreaming(agent, false);
      setAgentError(agent, String(error));
    }
  }

  return (
    <>
      <div className="chat-area">
        {chat.messages.length ? (
          chat.messages.map((item) => (
            <div className={`msg ${item.role === "user" ? "msg-user" : "msg-agent"}`} key={item._id}>
              {item.content || "生成中..."}
            </div>
          ))
        ) : (
          <div className="msg msg-agent">{welcomeText(agent)}</div>
        )}
      </div>
      {chat.error ? <div className="agent-error">{chat.error}</div> : null}
      {selectedText ? (
        <div className="input-quote-wrap show">
          <div className={`input-quote-tag ${agent}`}>
            <span className="input-quote-icon">→</span>
            <span className="input-quote-text">{selectedText}</span>
          </div>
        </div>
      ) : null}
      <div className="chat-input">
        <input disabled={chat.streaming} placeholder={placeholder} value={message} onChange={(event) => setMessage(event.target.value)} />
        <button className={`send-btn send-${agent}`} disabled={chat.streaming} onClick={handleSend} type="button">
          {chat.streaming ? "生成中" : "发送"}
        </button>
      </div>
    </>
  );
}

function AudiencePanel({ project, selectedText }: { project: Project; selectedText?: string }) {
  const { audience, openPersonaModal, setProject } = useAppStore();

  async function handleSelectPersona(personaId: string) {
    if (project.active_persona_id === personaId) return;
    const updated = await setActivePersona(project._id, project.user_id, personaId);
    setProject(updated);
  }

  return (
    <div className="panel-body">
      <div className="persona-bar">
        <span className="persona-label">画像</span>
        {project.personas.length ? (
          project.personas.map((persona) => (
            <PersonaChip
              key={persona.persona_id}
              persona={persona}
              active={project.active_persona_id === persona.persona_id}
              onSelect={() => handleSelectPersona(persona.persona_id)}
              onEdit={() => openPersonaModal({ mode: "edit", personaId: persona.persona_id })}
            />
          ))
        ) : (
          <span className="persona-empty">尚未创建任何 persona。</span>
        )}
        <button
          className="chip add-chip"
          onClick={() => openPersonaModal({ mode: "create" })}
          type="button"
          aria-label="新建 persona"
        >
          +
        </button>
      </div>
      <AudienceAnalysisCard project={project} />
      {audience.personaModal ? null : null}
      <AgentChat
        agent="audience"
        selectedText={selectedText}
        placeholder={
          project.active_persona_id
            ? "发送片段让观众评估..."
            : "请先选择或创建一个 persona 再发起对话..."
        }
      />
    </div>
  );
}

function PersonaChip({
  persona,
  active,
  onSelect,
  onEdit
}: {
  persona: Persona;
  active: boolean;
  onSelect: () => void;
  onEdit: () => void;
}) {
  return (
    <span className={`persona-chip ${active ? "active" : ""}`}>
      <button className="persona-chip-main" onClick={onSelect} type="button" title={persona.preferences || persona.behavior || persona.name}>
        {persona.icon ? <span className="persona-chip-icon">{persona.icon}</span> : null}
        <span className="persona-chip-name">{persona.name}</span>
      </button>
      <button
        className="persona-chip-edit"
        onClick={(event) => {
          event.stopPropagation();
          onEdit();
        }}
        type="button"
        aria-label={`编辑 ${persona.name}`}
        title="编辑"
      >
        ✎
      </button>
    </span>
  );
}

function AudienceAnalysisCard({ project }: { project: Project }) {
  const [expanded, setExpanded] = useState(true);
  const analysis = project.audience_analysis ?? {};
  const hasAnalysis = Boolean(analysis.updated_at);
  const stale = project.stale.audience;

  if (!hasAnalysis) {
    return (
      <div className="audience-card audience-card-empty">
        <span>与观众 Agent 对话以生成结构化分析。</span>
      </div>
    );
  }

  return (
    <div className={`audience-card ${stale ? "is-stale" : ""}`}>
      <button className="audience-card-header" onClick={() => setExpanded((value) => !value)} type="button">
        <span className="audience-card-title">
          观众分析 · {analysis.persona_name || "未指定 persona"}
        </span>
        <span className="audience-card-meta">
          {stale ? <span className="audience-card-stale">分析可能过期</span> : null}
          <ScoreChip label="自然度" score={analysis.naturalness_score} />
          <ScoreChip label="可信度" score={analysis.credibility_score} />
          <ScoreChip label="广告感" score={analysis.ad_sensitivity_score} />
          <IconChevron />
        </span>
      </button>
      {expanded ? <AudienceAnalysisBody analysis={analysis} /> : null}
    </div>
  );
}

function ScoreChip({ label, score }: { label: string; score?: number | null }) {
  if (typeof score !== "number") return null;
  const tone = score >= 4 ? "high" : score >= 3 ? "medium" : "low";
  return <span className={`audience-score audience-score-${tone}`}>{label} {score}/5</span>;
}

function AudienceAnalysisBody({ analysis }: { analysis: AudienceAnalysis }) {
  return (
    <div className="audience-card-body">
      {analysis.summary ? <p className="audience-summary">{analysis.summary}</p> : null}
      {analysis.key_risks?.length ? (
        <AnalysisListBlock title="关键风险" items={analysis.key_risks} />
      ) : null}
      {analysis.liked_parts?.length ? (
        <AnalysisRowsBlock title="观众喜欢" items={analysis.liked_parts} />
      ) : null}
      {analysis.rejected_parts?.length ? (
        <AnalysisRowsBlock title="观众反感" items={analysis.rejected_parts} />
      ) : null}
      {analysis.suggestions?.length ? (
        <AnalysisListBlock title="改进建议" items={analysis.suggestions} />
      ) : null}
    </div>
  );
}

function AnalysisListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="audience-block">
      <span className="audience-block-title">{title}</span>
      <ul>
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function AnalysisRowsBlock({ title, items }: { title: string; items: Array<{ row_id: string; reason: string }> }) {
  return (
    <div className="audience-block">
      <span className="audience-block-title">{title}</span>
      <ul>
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>
            <code>{item.row_id}</code> {item.reason ? `· ${item.reason}` : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function PersonaModalContainer() {
  const { audience, openPersonaModal, project, setProject } = useAppStore();
  if (!audience.personaModal || !project) return null;

  return (
    <PersonaModal
      mode={audience.personaModal.mode}
      persona={
        audience.personaModal.mode === "edit"
          ? project.personas.find((p) => p.persona_id === audience.personaModal?.personaId) ?? null
          : null
      }
      project={project}
      onClose={() => openPersonaModal(null)}
      onSaved={(updated) => {
        setProject(updated);
        openPersonaModal(null);
      }}
    />
  );
}

const AD_SENSITIVITY_OPTIONS: Array<{ value: PersonaAdSensitivity; label: string }> = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" }
];

function PersonaModal({
  mode,
  persona,
  project,
  onClose,
  onSaved
}: {
  mode: "create" | "edit";
  persona: Persona | null;
  project: Project;
  onClose: () => void;
  onSaved: (project: Project) => void;
}) {
  const [draft, setDraft] = useState<PersonaInput>(() => ({
    name: persona?.name ?? "",
    gender: persona?.gender ?? "",
    age_range: persona?.age_range ?? "",
    preferences: persona?.preferences ?? "",
    behavior: persona?.behavior ?? "",
    platform_context: persona?.platform_context ?? "",
    ad_sensitivity: persona?.ad_sensitivity ?? "medium",
    trust_trigger: persona?.trust_trigger ?? [],
    reject_trigger: persona?.reject_trigger ?? []
  }));
  const [trustText, setTrustText] = useState((persona?.trust_trigger ?? []).join(", "));
  const [rejectText, setRejectText] = useState((persona?.reject_trigger ?? []).join(", "));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function parseTriggers(text: string): string[] {
    return text
      .split(/[,，]/)
      .map((chunk) => chunk.trim())
      .filter(Boolean);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!draft.name.trim()) {
      setError("请填写 persona 名称。");
      return;
    }

    const payload: PersonaInput = {
      ...draft,
      name: draft.name.trim(),
      gender: (draft.gender ?? "").trim(),
      age_range: (draft.age_range ?? "").trim(),
      preferences: (draft.preferences ?? "").trim(),
      behavior: (draft.behavior ?? "").trim(),
      platform_context: (draft.platform_context ?? "").trim(),
      trust_trigger: parseTriggers(trustText),
      reject_trigger: parseTriggers(rejectText)
    };

    setSubmitting(true);
    setError(null);
    try {
      const updated =
        mode === "create"
          ? await createPersona(project._id, project.user_id, payload)
          : await updatePersona(project._id, project.user_id, persona!.persona_id, payload);
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!persona) return;
    if (!window.confirm(`确定删除 persona「${persona.name}」？`)) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await deletePersona(project._id, project.user_id, persona.persona_id);
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="persona-modal-backdrop" role="dialog" aria-modal="true">
      <form className="persona-modal" onSubmit={handleSubmit}>
        <header className="persona-modal-header">
          <h2>{mode === "create" ? "新建 Persona" : "编辑 Persona"}</h2>
          <button className="persona-modal-close" onClick={onClose} type="button" aria-label="关闭">
            ×
          </button>
        </header>
        <div className="persona-modal-body">
          <label>
            名称 *
            <input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} required />
          </label>
          <div className="persona-modal-row">
            <label>
              性别
              <input value={draft.gender ?? ""} onChange={(event) => setDraft({ ...draft, gender: event.target.value })} />
            </label>
            <label>
              年龄段 / 人群
              <input
                value={draft.age_range ?? ""}
                onChange={(event) => setDraft({ ...draft, age_range: event.target.value })}
                placeholder="例如 25-32 岁 / 大学生"
              />
            </label>
          </div>
          <label>
            偏好
            <textarea
              value={draft.preferences ?? ""}
              onChange={(event) => setDraft({ ...draft, preferences: event.target.value })}
              rows={2}
            />
          </label>
          <label>
            行为习惯
            <textarea
              value={draft.behavior ?? ""}
              onChange={(event) => setDraft({ ...draft, behavior: event.target.value })}
              rows={2}
            />
          </label>
          <label>
            常用平台
            <input
              value={draft.platform_context ?? ""}
              onChange={(event) => setDraft({ ...draft, platform_context: event.target.value })}
              placeholder="例如 小红书 / 抖音"
            />
          </label>
          <div className="persona-modal-row">
            <label>
              广告敏感度
              <select
                value={draft.ad_sensitivity ?? "medium"}
                onChange={(event) => setDraft({ ...draft, ad_sensitivity: event.target.value as PersonaAdSensitivity })}
              >
                {AD_SENSITIVITY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              信任触点（逗号分隔）
              <input value={trustText} onChange={(event) => setTrustText(event.target.value)} />
            </label>
            <label>
              抵触触点（逗号分隔）
              <input value={rejectText} onChange={(event) => setRejectText(event.target.value)} />
            </label>
          </div>
        </div>
        {error ? <div className="persona-modal-error">{error}</div> : null}
        <footer className="persona-modal-footer">
          {mode === "edit" ? (
            <button
              className="insight-delete-btn"
              disabled={submitting}
              onClick={handleDelete}
              type="button"
            >
              删除
            </button>
          ) : (
            <span />
          )}
          <div className="persona-modal-actions">
            <button className="topbar-btn" disabled={submitting} onClick={onClose} type="button">
              取消
            </button>
            <button className="pinned-add-btn" disabled={submitting} type="submit">
              {submitting ? "保存中..." : mode === "create" ? "创建" : "保存"}
            </button>
          </div>
        </footer>
      </form>
    </div>
  );
}

function ExpertPanel({ project, selectedText }: { project: Project; selectedText?: string }) {
  const { openDiffOverlay, setProject, setExpertApplyToast } = useAppStore();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const sorted = [...project.expert_suggestions].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

  async function handleDismiss(suggestion: ExpertSuggestion) {
    try {
      const updated = await updateExpertSuggestionStatus(project._id, project.user_id, suggestion.suggestion_id, "dismissed");
      setProject(updated);
    } catch (error) {
      setExpertApplyToast({
        tone: "error",
        message: `忽略方案失败：${error instanceof Error ? error.message : String(error)}`
      });
    }
  }

  return (
    <div className="panel-body">
      {sorted.length ? (
        <div className="expert-cards">
          {sorted.map((suggestion) => (
            <ExpertProposalCard
              key={suggestion.suggestion_id}
              suggestion={suggestion}
              project={project}
              expanded={expandedId === suggestion.suggestion_id}
              onToggleExpand={() => setExpandedId((id) => (id === suggestion.suggestion_id ? null : suggestion.suggestion_id))}
              onPreview={() => openDiffOverlay(suggestion.suggestion_id)}
              onDismiss={() => handleDismiss(suggestion)}
            />
          ))}
        </div>
      ) : (
        <div className="expert-empty">
          {project.stale.expert
            ? "品牌 / 观众的输入有更新。向专家 Agent 发起对话以生成新的多方案。"
            : "向专家 Agent 描述需求或选中文本提问，专家会生成多个 cell-level 修改方案。"}
        </div>
      )}
      <AgentChat agent="expert" selectedText={selectedText} placeholder="向专家 Agent 提问，生成多方向修改建议..." />
    </div>
  );
}

const DIRECTION_LABEL: Record<ExpertDirection, string> = {
  brand_first: "品牌优先",
  audience_natural: "观众自然",
  balanced: "平衡取舍",
  creator_expression: "创作者表达",
  custom: "自定义"
};

function ExpertProposalCard({
  suggestion,
  project,
  expanded,
  onToggleExpand,
  onPreview,
  onDismiss
}: {
  suggestion: ExpertSuggestion;
  project: Project;
  expanded: boolean;
  onToggleExpand: () => void;
  onPreview: () => void;
  onDismiss: () => void;
}) {
  const isActionable = suggestion.status === "draft" || suggestion.status === "partially_applied";
  return (
    <article className={`expert-card expert-direction-${suggestion.direction} status-${suggestion.status}`}>
      <header className="expert-card-top">
        <span className={`expert-direction-chip dir-${suggestion.direction}`}>
          {DIRECTION_LABEL[suggestion.direction] ?? "自定义"}
        </span>
        <span className="expert-card-title">{suggestion.title}</span>
        <span className={`expert-card-status status-${suggestion.status}`}>{expertStatusLabel(suggestion.status)}</span>
      </header>
      {suggestion.description ? <p className="expert-card-desc">{suggestion.description}</p> : null}
      <div className="expert-card-actions">
        <button className="prop-btn prop-btn-primary" onClick={onPreview} type="button" disabled={!isActionable}>
          <IconEye />
          {suggestion.status === "applied" ? "重新预览" : "预览修改"}
        </button>
        <button className="prop-btn" onClick={onToggleExpand} type="button">
          {expanded ? "收起详情" : "展开详情"}
        </button>
        {isActionable ? (
          <button className="prop-btn prop-btn-ghost" onClick={onDismiss} type="button" title="忽略此方案">
            忽略
          </button>
        ) : null}
      </div>
      {expanded ? <ExpertProposalDetails suggestion={suggestion} project={project} /> : null}
    </article>
  );
}

function ExpertProposalDetails({ suggestion, project }: { suggestion: ExpertSuggestion; project: Project }) {
  const columnsLabel = useColumnLabelLookup(project.current_script);
  return (
    <div className="expert-card-details">
      {suggestion.target_problem ? (
        <DetailRow label="解决问题" value={suggestion.target_problem} />
      ) : null}
      {suggestion.rationale ? <DetailRow label="推理理由" value={suggestion.rationale} /> : null}
      {(suggestion.brand_tradeoff || suggestion.audience_tradeoff || suggestion.creator_tradeoff) ? (
        <div className="expert-tradeoff-grid">
          <TradeoffCell label="品牌" value={suggestion.brand_tradeoff} />
          <TradeoffCell label="观众" value={suggestion.audience_tradeoff} />
          <TradeoffCell label="创作者" value={suggestion.creator_tradeoff} />
        </div>
      ) : null}
      {suggestion.risk ? <DetailRow label="风险" value={suggestion.risk} /> : null}
      {suggestion.explanation_to_brand ? (
        <DetailRow label="对品牌的解释话术" value={suggestion.explanation_to_brand} />
      ) : null}
      <div className="expert-hunks-summary">
        <span className="expert-block-title">cell-level 修改（{suggestion.hunks.length} 个 hunk）</span>
        <ul>
          {suggestion.hunks.map((hunk) => (
            <li key={hunk.hunk_id}>
              <code>{hunk.row_id}</code> · {columnsLabel(hunk.column_id)}
              {hunk.reason ? <span className="expert-hunk-reason"> · {hunk.reason}</span> : null}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="expert-detail-row">
      <span className="expert-block-title">{label}</span>
      <p>{value}</p>
    </div>
  );
}

function TradeoffCell({ label, value }: { label: string; value: string }) {
  if (!value) return <div className="expert-tradeoff-cell expert-tradeoff-cell-empty">{label}：暂无</div>;
  return (
    <div className="expert-tradeoff-cell">
      <span className="expert-tradeoff-label">{label}</span>
      <p>{value}</p>
    </div>
  );
}

function expertStatusLabel(status: ExpertSuggestion["status"]) {
  if (status === "applied") return "已应用";
  if (status === "partially_applied") return "部分应用";
  if (status === "dismissed") return "已忽略";
  return "待预览";
}

function useColumnLabelLookup(script: Script): (columnId: string) => string {
  const map = new Map<string, string>();
  for (const column of script.columns) {
    map.set(column.column_id, column.label);
  }
  return (columnId: string) => map.get(columnId) ?? columnId;
}

function DiffOverlayContainer() {
  const { expert, project, closeDiffOverlay, setProject, setHunkState, setAllHunks, resetHunkState, setExpertConflicts, setExpertApplyToast } = useAppStore();
  const [submitting, setSubmitting] = useState(false);

  if (!project || !expert.diffOverlayOpen || !expert.activeSuggestionId) return null;
  const suggestion = project.expert_suggestions.find((item) => item.suggestion_id === expert.activeSuggestionId);
  if (!suggestion) return null;

  const columnLabel = useColumnLabelLookup(project.current_script);
  const acceptedIds = suggestion.hunks.filter((hunk) => expert.hunkState[hunk.hunk_id] === true).map((hunk) => hunk.hunk_id);
  const rejectedIds = suggestion.hunks.filter((hunk) => expert.hunkState[hunk.hunk_id] === false).map((hunk) => hunk.hunk_id);

  async function handleApply() {
    if (!project) return;
    if (acceptedIds.length === 0) {
      setExpertApplyToast({ tone: "warning", message: "至少标记一个 hunk 为「应用」后再写入编辑器。" });
      window.setTimeout(() => setExpertApplyToast(undefined), 4000);
      return;
    }
    setSubmitting(true);
    try {
      const result = await applyExpertSuggestion(project._id, project.user_id, suggestion.suggestion_id, {
        accepted_hunk_ids: acceptedIds,
        rejected_hunk_ids: rejectedIds
      });
      setProject(result.project);

      if (result.applied_hunk_count === 0) {
        setExpertConflicts(result.conflict_hunk_ids);
        setExpertApplyToast({
          tone: "error",
          message: "所有 hunk 与当前脚本不一致，建议重新生成方案。"
        });
        return;
      }
      if (result.conflict_hunk_ids.length > 0) {
        setExpertConflicts(result.conflict_hunk_ids);
        setExpertApplyToast({
          tone: "warning",
          message: `已应用 ${result.applied_hunk_count} 个 hunk，${result.conflict_hunk_ids.length} 个与脚本不一致已跳过。`
        });
      } else {
        setExpertApplyToast({
          tone: "success",
          message: `已写入 ${result.applied_hunk_count} 个 hunk 到脚本。`
        });
      }
      window.setTimeout(() => setExpertApplyToast(undefined), 5000);
      closeDiffOverlay();
    } catch (error) {
      setExpertApplyToast({
        tone: "error",
        message: `应用失败：${error instanceof Error ? error.message : String(error)}`
      });
    } finally {
      setSubmitting(false);
    }
  }

  const allHunkIds = suggestion.hunks.map((h) => h.hunk_id);

  return (
    <div className="diff-overlay-backdrop" role="dialog" aria-modal="true">
      <div className="diff-overlay">
        <header className="diff-overlay-header">
          <div>
            <span className={`expert-direction-chip dir-${suggestion.direction}`}>{DIRECTION_LABEL[suggestion.direction] ?? "自定义"}</span>
            <strong className="diff-overlay-title">{suggestion.title}</strong>
            <span className="diff-overlay-meta">{suggestion.hunks.length} 个 hunk · {acceptedIds.length} 已应用 / {rejectedIds.length} 已拒绝</span>
          </div>
          <button className="diff-overlay-close" onClick={closeDiffOverlay} type="button" aria-label="关闭">
            ×
          </button>
        </header>
        <div className="diff-overlay-actions">
          <button className="prop-btn" onClick={() => setAllHunks(allHunkIds, true)} type="button">全部应用</button>
          <button className="prop-btn" onClick={() => setAllHunks(allHunkIds, false)} type="button">全部不应用</button>
          <button className="prop-btn prop-btn-ghost" onClick={resetHunkState} type="button">重置</button>
          <div className="diff-overlay-spacer" />
          <button
            className="prop-btn prop-btn-primary"
            onClick={handleApply}
            type="button"
            disabled={submitting}
          >
            {submitting ? "写入中..." : `写入编辑器（${acceptedIds.length}）`}
          </button>
        </div>
        <div className="diff-overlay-body">
          {suggestion.hunks.map((hunk, index) => (
            <HunkCard
              key={hunk.hunk_id}
              index={index}
              hunk={hunk}
              columnLabel={columnLabel(hunk.column_id)}
              state={expert.hunkState[hunk.hunk_id] ?? null}
              conflict={expert.conflicts.includes(hunk.hunk_id)}
              onAccept={() => setHunkState(hunk.hunk_id, true)}
              onReject={() => setHunkState(hunk.hunk_id, false)}
              onClear={() => setHunkState(hunk.hunk_id, null)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function HunkCard({
  index,
  hunk,
  columnLabel,
  state,
  conflict,
  onAccept,
  onReject,
  onClear
}: {
  index: number;
  hunk: ExpertHunk;
  columnLabel: string;
  state: true | false | null;
  conflict: boolean;
  onAccept: () => void;
  onReject: () => void;
  onClear: () => void;
}) {
  const stateClass = state === true ? "is-accepted" : state === false ? "is-rejected" : "is-pending";
  return (
    <div className={`hunk-card ${stateClass} ${conflict ? "is-conflict" : ""}`}>
      <header className="hunk-card-header">
        <span className="hunk-card-index">#{String(index + 1).padStart(2, "0")}</span>
        <code>{hunk.row_id}</code>
        <span className="hunk-card-column">{columnLabel}</span>
        <span className={`hunk-card-state state-${stateClass}`}>{hunkStateLabel(state)}</span>
        {conflict ? <span className="hunk-card-conflict">脚本已变化</span> : null}
      </header>
      <div className="hunk-card-diff">
        <div className="hunk-old">
          <span className="hunk-side-label">原</span>
          <pre>{hunk.old || "（空）"}</pre>
        </div>
        <div className="hunk-new">
          <span className="hunk-side-label">新</span>
          <pre>{hunk.new || "（空）"}</pre>
        </div>
      </div>
      {hunk.reason ? <p className="hunk-reason">说明：{hunk.reason}</p> : null}
      <div className="hunk-card-actions">
        <button
          className={`prop-btn ${state === true ? "prop-btn-primary" : ""}`}
          onClick={state === true ? onClear : onAccept}
          type="button"
        >
          ✓ 应用
        </button>
        <button
          className={`prop-btn ${state === false ? "prop-btn-warning" : ""}`}
          onClick={state === false ? onClear : onReject}
          type="button"
        >
          ✗ 不应用
        </button>
      </div>
    </div>
  );
}

function hunkStateLabel(state: true | false | null) {
  if (state === true) return "应用";
  if (state === false) return "不应用";
  return "未决定";
}

function SnapshotsDrawer() {
  const {
    project,
    snapshots,
    setSnapshots,
    setSnapshotsError,
    setSnapshotsLoading,
    setSnapshotsOpen,
    setProject,
    setExpertApplyToast
  } = useAppStore();
  const [restoringId, setRestoringId] = useState<string | null>(null);

  useEffect(() => {
    if (!snapshots.open || !project) return;
    setSnapshotsLoading(true);
    setSnapshotsError(undefined);
    listScriptSnapshots(project._id, project.user_id)
      .then((items) => setSnapshots(items))
      .catch((error) => setSnapshotsError(error instanceof Error ? error.message : String(error)))
      .finally(() => setSnapshotsLoading(false));
  }, [snapshots.open, project, setSnapshots, setSnapshotsError, setSnapshotsLoading]);

  if (!snapshots.open || !project) return null;

  async function handleRestore(snapshotId: string) {
    if (!project) return;
    if (!window.confirm("回退到此版本会覆盖当前脚本（系统会先保存当前版本）。是否继续？")) return;
    setRestoringId(snapshotId);
    try {
      const updated = await restoreScriptSnapshot(project._id, project.user_id, snapshotId);
      setProject(updated);
      setSnapshotsOpen(false);
      setExpertApplyToast({ tone: "success", message: "脚本已回退到该版本。" });
      window.setTimeout(() => setExpertApplyToast(undefined), 5000);
    } catch (error) {
      setExpertApplyToast({
        tone: "error",
        message: `回退失败：${error instanceof Error ? error.message : String(error)}`
      });
    } finally {
      setRestoringId(null);
    }
  }

  return (
    <div className="snapshot-drawer-backdrop" role="dialog" aria-modal="true" onClick={() => setSnapshotsOpen(false)}>
      <aside className="snapshot-drawer" onClick={(event) => event.stopPropagation()}>
        <header className="snapshot-drawer-header">
          <h2>版本历史</h2>
          <button className="persona-modal-close" onClick={() => setSnapshotsOpen(false)} type="button" aria-label="关闭">
            ×
          </button>
        </header>
        <div className="snapshot-drawer-body">
          {snapshots.loading ? <div className="snapshot-empty">加载中...</div> : null}
          {snapshots.error ? <div className="snapshot-error">{snapshots.error}</div> : null}
          {!snapshots.loading && !snapshots.error && snapshots.items.length === 0 ? (
            <div className="snapshot-empty">暂无版本快照。专家方案应用或手动保存后会出现在这里。</div>
          ) : null}
          {snapshots.items.map((snapshot) => (
            <SnapshotRow
              key={snapshot._id}
              snapshot={snapshot}
              restoring={restoringId === snapshot._id}
              onRestore={() => handleRestore(snapshot._id)}
            />
          ))}
        </div>
      </aside>
    </div>
  );
}

function SnapshotRow({
  snapshot,
  restoring,
  onRestore
}: {
  snapshot: ScriptSnapshotSummary;
  restoring: boolean;
  onRestore: () => void;
}) {
  return (
    <div className="snapshot-item">
      <div className="snapshot-item-main">
        <span className={`snapshot-reason snapshot-reason-${snapshot.reason}`}>{snapshotReasonLabel(snapshot.reason)}</span>
        <span className="snapshot-time">{snapshot.created_at}</span>
      </div>
      {snapshot.applied_hunk_ids.length ? (
        <div className="snapshot-item-meta">应用了 {snapshot.applied_hunk_ids.length} 个 hunk</div>
      ) : null}
      <button className="prop-btn" disabled={restoring} onClick={onRestore} type="button">
        {restoring ? "回退中..." : "回退到此版本"}
      </button>
    </div>
  );
}

function snapshotReasonLabel(reason: ScriptSnapshotSummary["reason"]) {
  if (reason === "manual_save") return "手动保存";
  if (reason === "before_expert_apply") return "应用前";
  if (reason === "after_expert_apply") return "应用后";
  if (reason === "before_restore") return "回退前";
  if (reason === "import") return "导入";
  return reason;
}

function LegacyAgentChat({ agent, selectedText, placeholder }: { agent: AgentType; selectedText?: string; placeholder: string }) {
  const { project, setProject } = useAppStore();
  const [message, setMessage] = useState("");

  async function handleSend() {
    if (!project || !message.trim()) return;

    if (agent === "brand") {
      const savedProject = await createBrandInsight(project._id, project.user_id, {
        category: "brand_feedback",
        title: "PR feedback",
        content: message.trim(),
        reason: selectedText ? "用户基于选中脚本片段补充的品牌反馈。" : "用户在品牌方 Agent 对话中输入的反馈。",
        evidence: selectedText ? [{ source_type: "script", quote: selectedText }] : [{ source_type: "chat", quote: message.trim() }],
        confidence: "medium",
        status: "pending"
      });
      setProject(savedProject);
    }

    setMessage("");
  }

  return (
    <>
      <div className="chat-area">
        <div className="msg msg-agent">{welcomeText(agent)}</div>
      </div>
      {selectedText ? (
        <div className="input-quote-wrap show">
          <div className={`input-quote-tag ${agent}`}>
            <span className="input-quote-icon">↳</span>
            <span className="input-quote-text">{selectedText}</span>
          </div>
        </div>
      ) : null}
      <div className="chat-input">
        <input placeholder={placeholder} value={message} onChange={(event) => setMessage(event.target.value)} />
        <button className={`send-btn send-${agent}`} onClick={handleSend} type="button">发送</button>
      </div>
    </>
  );
}

function welcomeText(agent: AgentType) {
  if (agent === "brand") return "我会从品牌安全、卖点表达和 brief 一致性角度检查当前脚本。";
  if (agent === "audience") return "我会模拟目标观众，判断片段的真实感、广告感和信息密度。";
  return "我会综合多方反馈，给出可预览、可确认的 cell-level 修改建议。";
}

function statusClass(status: string) {
  if (status === "editing" || status === "saving") return "editing";
  if (status === "failed") return "failed";
  return "saved";
}

function statusLabel(status: string) {
  if (status === "editing") return "编辑中";
  if (status === "saving") return "保存中";
  if (status === "failed") return "保存失败";
  return "已保存";
}

function confidenceLabel(confidence: BrandInsightConfidence) {
  if (confidence === "high") return "高";
  if (confidence === "low") return "低";
  return "中";
}

function statusLabelInsight(status: BrandInsightStatus) {
  if (status === "confirmed") return "已确认";
  if (status === "pending") return "待确认";
  if (status === "ignored") return "忽略";
  return "新增";
}

function IconUpload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

function IconEye() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function IconEdit() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="9 11 12 14 22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}

function IconChevron() {
  return (
    <svg className="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function IconBack() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M19 12H5" />
      <path d="M12 19l-7-7 7-7" />
    </svg>
  );
}

function IconHistory() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <polyline points="3 4 3 10 9 10" />
      <polyline points="12 7 12 12 16 14" />
    </svg>
  );
}
