"use client";

import { useEffect, useRef, useState } from "react";

import { ScriptGrid } from "@/components/ScriptGrid";
import {
  createBrandInsight,
  deleteBrandInsight,
  fetchAgentMessages,
  fetchProject,
  saveBrief,
  saveScript,
  streamAgentMessage,
  updateBrandInsight
} from "@/lib/api";
import type {
  AgentMessage,
  AgentQuote,
  AgentType,
  BrandInsight,
  BrandInsightCategory,
  BrandInsightConfidence,
  BrandInsightStatus,
  Project
} from "@/lib/types";
import { useAppStore } from "@/store/appStore";

const SAVE_DELAY_MS = 700;

const AGENTS: Array<{
  type: AgentType;
  title: string;
  badge: string;
  badgeClass: string;
  tone: "brand" | "audience" | "expert";
}> = [
  { type: "brand", title: "品牌方 Agent", badge: "分析完成", badgeClass: "badge-done", tone: "brand" },
  { type: "audience", title: "观众 Agent", badge: "待触发", badgeClass: "badge-wait", tone: "audience" },
  { type: "expert", title: "专家 Agent", badge: "有新输入", badgeClass: "badge-new", tone: "expert" }
];

function brandAgentBadge(project: Project) {
  const st = project.brand_research?.status;
  if (st === "running") return { label: "Brief 分析中", badgeClass: "badge-wait" as const };
  if (st === "failed") return { label: "Brief 分析失败", badgeClass: "badge-new" as const };
  if (st === "done") return { label: "分析完成", badgeClass: "badge-done" as const };
  return { label: "待 Brief", badgeClass: "badge-wait" as const };
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
    setAgentColumnWidth,
    setBrandPinnedTab,
    setProject,
    setSaveStatus,
    setUserId,
    openPanel
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
        <button className="topbar-btn" type="button">
          <IconEye />
          预览修改稿
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
          const brandBadge = agent.type === "brand" ? brandAgentBadge(project) : null;
          const badgeLabel = brandBadge?.label ?? agent.badge;
          const badgeClass = brandBadge?.badgeClass ?? agent.badgeClass;
          return (
            <section
              className={`agent-panel panel-${agent.tone} ${activePanel === agent.type ? "expanded" : "collapsed"}`}
              key={agent.type}
            >
              <button className="panel-header" onClick={() => openPanel(agent.type)} type="button">
                <span className={`panel-dot dot-${agent.tone}`} />
                <span className={`panel-name name-${agent.tone}`}>{agent.title}</span>
                <span
                  className={`panel-badge ${agent.type === "brand" ? badgeClass : agent.type === "audience" ? "badge-wait" : "badge-new"}`}
                >
                  {agent.type === "brand" ? badgeLabel : agent.badge}
                </span>
                <IconChevron />
              </button>
              {activePanel === agent.type ? <AgentBody agent={agent.type} selectedText={editor.selectedText} /> : null}
            </section>
          );
        })}
      </aside>
    </main>
  );
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

  if (agent === "audience") {
    return (
      <div className="panel-body">
        <div className="persona-bar">
          <span className="persona-label">画像</span>
          <button className="chip active" type="button">年轻职场人</button>
          <button className="chip" type="button">首次购车</button>
          <button className="chip add-chip" type="button">+</button>
        </div>
        <AgentChat agent="audience" selectedText={selectedText} placeholder="发送片段让观众评估..." />
      </div>
    );
  }

  return (
    <div className="panel-body">
      <div className="chat-area compact">
        <div className="msg msg-agent">已综合品牌方与观众反馈，生成两个修改方向，预览后可进入 Diff 确认。</div>
      </div>
      <div className="proposals">
        <div className="proposal-card">
          <div className="proposal-top">
            <span className="proposal-title">方向一：强化真实感</span>
            <span className="proposal-rec">推荐</span>
          </div>
          <div className="proposal-desc">把抽象表达改成账单、路况、缺点等具体细节，提高可信度。</div>
          <div className="proposal-actions">
            <button className="prop-btn prop-btn-primary" type="button">
              <IconEye />
              预览修改
            </button>
          </div>
        </div>
      </div>
      <AgentChat agent="expert" selectedText={selectedText} placeholder="向专家 Agent 提问..." />
    </div>
  );
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

    try {
      await streamAgentMessage(
        project._id,
        agent,
        { user_id: project.user_id, content, quotes },
        {
          onToken: (token) => appendAssistantToken(agent, assistantId, token),
          onDone: async () => {
            setAgentStreaming(agent, false);
            setAgentMessages(agent, await fetchAgentMessages(project._id, project.user_id, agent));
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
