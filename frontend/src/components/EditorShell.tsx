"use client";

import { useEffect, useRef } from "react";

import { ScriptGrid } from "@/components/ScriptGrid";
import { saveScript } from "@/lib/api";
import type { AgentType } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

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

export function EditorShell() {
  const {
    editor,
    layout,
    project,
    script,
    setAgentColumnWidth,
    setProject,
    setSaveStatus,
    setUserId,
    openPanel
  } = useAppStore();
  const hasHydrated = useRef(false);
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

  if (!project || !script) return null;

  return (
    <main className="app" style={{ "--agents-col-width": `${layout.agentsColWidth}px` } as React.CSSProperties}>
      <header className="topbar">
        <button className="topbar-btn" onClick={handleBack} type="button">
          <IconBack />
          项目
        </button>
        <span className="logo">Creator Studio</span>
        <button className="topbar-btn" type="button">
          <IconUpload />
          上传品牌 Brief
        </button>
        <span className="topbar-brief-hint">MD / TXT</span>
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
        aria-label="拖拽调整脚本编辑器与 Agent 面板宽度"
      />

      <aside className="agents-col">
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
      </aside>
    </main>
  );
}

function AgentBody({ agent, selectedText }: { agent: AgentType; selectedText?: string }) {
  if (agent === "brand") {
    return (
      <div className="panel-body">
        <div className="pinned">
          <div className="pinned-tabs">
            <button className="ptab active-brand" type="button">显式需求</button>
            <button className="ptab" type="button">隐式需求</button>
            <button className="ptab" type="button">品牌反馈</button>
          </div>
          <div className="pinned-content show">
            <div className="pinned-list">
              <PinnedItem mark="01" text="口播要保留真实体验感，避免像硬广。" tone="blue" />
              <PinnedItem mark="02" text="突出具体使用场景和可验证细节。" tone="blue" />
            </div>
            <div className="pinned-add-row">
              <button className="pinned-add-btn" type="button">+ 添加需求</button>
            </div>
          </div>
        </div>
        <AgentChat agent="brand" selectedText={selectedText} placeholder="向品牌方 Agent 提问..." />
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

function PinnedItem({ mark, text, tone }: { mark: string; text: string; tone: "blue" | "warn" }) {
  return (
    <div className="pinned-item">
      <span className={`pinned-item-mark mark-${tone}`}>{mark}</span>
      <span className="pinned-item-text">{text}</span>
    </div>
  );
}

function AgentChat({ agent, selectedText, placeholder }: { agent: AgentType; selectedText?: string; placeholder: string }) {
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
        <input placeholder={placeholder} readOnly value="" />
        <button className={`send-btn send-${agent}`} type="button">发送</button>
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
