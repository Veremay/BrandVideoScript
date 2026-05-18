"use client";

import { useEffect, useRef } from "react";

import { saveScript } from "@/lib/api";
import { useAppStore } from "@/store/appStore";
import { ScriptGrid } from "@/components/ScriptGrid";

const SAVE_DELAY_MS = 700;

export function EditorShell() {
  const { editor, layout, project, script, setProject, setSaveStatus, setUserId, openPanel } = useAppStore();
  const hasHydrated = useRef(false);

  useEffect(() => {
    if (!project || !script) {
      return;
    }

    if (!hasHydrated.current) {
      hasHydrated.current = true;
      return;
    }

    if (editor.saveStatus !== "editing") {
      return;
    }

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

  if (!project || !script) {
    return null;
  }

  return (
    <main className="editorShell">
      <header className="topbar">
        <button className="ghostButton" onClick={handleBack}>
          返回项目
        </button>
        <div className="titleBlock">
          <span>Creator Studio</span>
          <input value={project.title} readOnly aria-label="项目名称" />
        </div>
        <div className={`savePill ${editor.saveStatus}`}>{statusLabel(editor.saveStatus)}</div>
        <button className="ghostButton" onClick={handleLogout}>
          退出
        </button>
      </header>

      <section className="workspace">
        <section className="scriptPane">
          <div className="paneHeader">
            <div>
              <p className="eyebrow">Script Editor</p>
              <h2>脚本草稿</h2>
            </div>
            <span className="muted">Phase 0 最小编辑网格</span>
          </div>
          <ScriptGrid script={script} />
        </section>

        <div className="divider" />

        <aside className="agentPane" style={{ width: layout.agentsColWidth }}>
          {(["brand", "audience", "expert"] as const).map((agent) => (
            <section className="agentSection" key={agent}>
              <button className="agentHeader" onClick={() => openPanel(agent)}>
                <span>{agentLabel(agent)}</span>
                <span>{layout.activePanel === agent ? "收起" : "展开"}</span>
              </button>
              {layout.activePanel === agent ? (
                <div className="agentBody">
                  <p>{agentLabel(agent)} 面板将在后续 Phase 接入真实 Agent。</p>
                </div>
              ) : null}
            </section>
          ))}
        </aside>
      </section>
    </main>
  );
}

function statusLabel(status: string) {
  if (status === "editing") return "编辑中";
  if (status === "saving") return "保存中";
  if (status === "failed") return "保存失败";
  return "已保存";
}

function agentLabel(agent: "brand" | "audience" | "expert") {
  if (agent === "brand") return "品牌方 Agent";
  if (agent === "audience") return "观众 Agent";
  return "专家 Agent";
}

