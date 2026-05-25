"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { ScriptGrid } from "@/components/ScriptGrid";
import {
  createBrandInsight,
  deleteBrandInsight,
  saveBrief,
  saveScript,
  updateBrandInsight
} from "@/lib/api";
import type { AgentType, BrandInsight, BrandInsightCategory, BrandInsightConfidence, BrandInsightStatus } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

const MapView = dynamic(() => import("@/components/MapView").then((mod) => mod.MapView), {
  ssr: false,
  loading: () => <main className="centerStage">Loading Map...</main>
});

const SAVE_DELAY_MS = 700;

const AGENTS: Array<{
  type: AgentType;
  title: string;
  badge: string;
  tone: "brand" | "audience" | "expert";
}> = [
  { type: "brand", title: "品牌方 Agent", badge: "分析完成", tone: "brand" },
  { type: "audience", title: "观众 Agent", badge: "待触发", tone: "audience" },
  { type: "expert", title: "专家 Agent", badge: "有新输入", tone: "expert" }
];

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
    setBrandPinnedTab,
    setProject,
    setSaveStatus,
    setUserId,
    setActivePanel,
    openPanel
  } = useAppStore();
  const hasHydrated = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
  const [activeView, setActiveView] = useState<"editor" | "map">("editor");
  const activePanel = layout.activePanel;

  useEffect(() => {
    if (layout.activePanel) {
      setAgentDrawerOpen(true);
    }
  }, [layout.activePanel]);

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

  function handleBack() {
    setProject(null);
  }

  function handleLogout() {
    window.localStorage.removeItem("brandvideo:user_id");
    setUserId(undefined);
    setProject(null);
  }

  function handleFabClick() {
    if (agentDrawerOpen) {
      setAgentDrawerOpen(false);
      return;
    }
    setAgentDrawerOpen(true);
    if (!layout.activePanel) {
      setActivePanel("brand");
    }
  }

  function handlePersonasClick() {
    setAgentDrawerOpen(true);
    setActivePanel("audience");
  }

  async function persistBrief(text: string, filename?: string) {
    if (!project) return;
    const savedProject = await saveBrief(project._id, project.user_id, text, filename);
    setProject(savedProject);
    setBrandPinnedTab("explicit_requirement");
    setAgentDrawerOpen(true);
    setActivePanel("brand");
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
    <main className="app-figma">
      <header className="figma-topnav">
        <div className="figma-topnav-left">
          <button className="figma-nav-btn figma-nav-back" onClick={handleBack} type="button">
            <IconBack />
            Back
          </button>
          <span className="figma-brand-logo">BrandVideo</span>
          <div className="figma-view-toggle" role="tablist" aria-label="Switch view">
            <button
              className={`figma-view-tab ${activeView === "editor" ? "active" : ""}`}
              onClick={() => setActiveView("editor")}
              type="button"
              aria-selected={activeView === "editor"}
            >
              <IconEditorList />
              Editor
            </button>
            <button
              className={`figma-view-tab ${activeView === "map" ? "active" : ""}`}
              onClick={() => setActiveView("map")}
              type="button"
              aria-selected={activeView === "map"}
            >
              <IconMap />
              Map
            </button>
          </div>
        </div>

        <div className="figma-topnav-right">
          <input ref={fileInputRef} accept=".md,.txt,text/markdown,text/plain" hidden onChange={handleBriefFile} type="file" />
          <button className="figma-nav-btn figma-nav-outline" onClick={() => fileInputRef.current?.click()} type="button">
            <IconUpload />
            Upload Brief
          </button>
          {project.brief.filename ? <span className="figma-brief-tag">{project.brief.filename}</span> : null}
          <button className="figma-nav-btn figma-nav-outline" onClick={handlePersonasClick} type="button">
            <IconPersonas />
            Personas
          </button>
          <button className="figma-icon-btn" type="button" aria-label="通知">
            <IconBell />
          </button>
          <button className="figma-icon-btn" onClick={handleLogout} title="退出登录" type="button" aria-label="设置">
            <IconSettings />
          </button>
          <button className="figma-nav-btn figma-nav-outline figma-nav-share" type="button">
            Share
          </button>
          <div className={`figma-save-pill status-${statusClass(editor.saveStatus)}`}>{statusLabel(editor.saveStatus)}</div>
          <button className="figma-nav-btn figma-nav-primary" type="button">
            Export
          </button>
          <button className="figma-avatar-btn" onClick={handleLogout} title={project.title} type="button" aria-label="用户">
            <span className="figma-avatar-fallback">{project.title.slice(0, 1).toUpperCase()}</span>
          </button>
        </div>
      </header>

      <section className="figma-main">
        {activeView === "editor" ? (
          <div className="editor-workspace">
            <div className="editor-page-header">
              <h1 className="editor-page-title">Script Editor</h1>
              <p className="editor-page-subtitle">{project.title}</p>
            </div>
            <ScriptGrid script={script} />
          </div>
        ) : (
          <MapView />
        )}
      </section>

      <button className="figma-fab" onClick={handleFabClick} type="button" aria-label="打开 Agent 对话">
        <IconLightning />
      </button>

      {agentDrawerOpen ? (
        <>
          <button className="figma-drawer-backdrop" onClick={() => setAgentDrawerOpen(false)} type="button" aria-label="关闭 Agent 面板" />
          <aside className="figma-agent-drawer">
            <div className="figma-drawer-header">
              <span className="figma-drawer-title">Agents</span>
              <button className="figma-drawer-close" onClick={() => setAgentDrawerOpen(false)} type="button" aria-label="关闭">
                ×
              </button>
            </div>
            <div className="figma-agent-stack">
              {AGENTS.map((agent) => (
                <section
                  className={`agent-panel panel-${agent.tone} ${activePanel === agent.type ? "expanded" : "collapsed"}`}
                  key={agent.type}
                >
                  <button className="panel-header" onClick={() => openPanel(agent.type)} type="button">
                    <span className={`panel-dot dot-${agent.tone}`} />
                    <span className={`panel-name name-${agent.tone}`}>{agent.title}</span>
                    <span className={`panel-badge ${agent.type === "brand" ? "badge-done" : agent.type === "audience" ? "badge-wait" : "badge-new"}`}>
                      {agent.badge}
                    </span>
                    <IconChevron />
                  </button>
                  {activePanel === agent.type ? <AgentBody agent={agent.type} selectedText={editor.selectedText} /> : null}
                </section>
              ))}
            </div>
          </aside>
        </>
      ) : null}
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
  if (status === "editing") return "Editing";
  if (status === "saving") return "Saving";
  if (status === "failed") return "Failed";
  return "Saved";
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
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

function IconEye() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function IconChevron() {
  return (
    <svg className="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function IconBack() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M19 12H5" />
      <path d="M12 19l-7-7 7-7" />
    </svg>
  );
}

function IconEditorList() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="8" x2="21" y1="6" y2="6" />
      <line x1="8" x2="21" y1="12" y2="12" />
      <line x1="8" x2="21" y1="18" y2="18" />
      <line x1="3" x2="3.01" y1="6" y2="6" />
      <line x1="3" x2="3.01" y1="12" y2="12" />
      <line x1="3" x2="3.01" y1="18" y2="18" />
    </svg>
  );
}

function IconMap() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <circle cx="5" cy="7" r="2" />
      <circle cx="19" cy="7" r="2" />
      <circle cx="7" cy="19" r="2" />
      <line x1="12" x2="5" y1="12" y2="7" />
      <line x1="12" x2="19" y1="12" y2="7" />
      <line x1="12" x2="7" y1="12" y2="19" />
    </svg>
  );
}

function IconPersonas() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function IconBell() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function IconLightning() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}
