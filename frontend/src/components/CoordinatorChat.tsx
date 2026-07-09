"use client";

import { useEffect, useRef, useState } from "react";

import { RevisionProposalsActions, RevisionProposalsList } from "@/components/RevisionProposalsPanel";
import { fetchCoordinatorMessages, streamCoordinatorMessage } from "@/lib/api";
import { resolveCoordinatorTaskType } from "@/lib/coordinatorIntent";
import type { CoordinatorMessage } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

type AssistantTab = "chat" | "plans";

const WELCOME_BASE = {
  message_id: "welcome",
  project_id: "",
  user_id: "",
  role: "assistant" as const,
  task_type: "user_message" as const,
  requested_perspectives: ["comprehensive" as const],
  quotes: [],
  related_node_ids: [],
  generated_artifact_ids: [],
  created_at: new Date().toISOString()
};

const WELCOME_FULL: CoordinatorMessage = {
  ...WELCOME_BASE,
  content:
    "Hi, I'm the Coordinator. Quote script to analyze nodes, or ask me to generate multi-direction revision proposals — Expert will add script revision options (not nodes) to Revision Proposals for preview and partial apply."
};

const WELCOME_VANILLA: CoordinatorMessage = {
  ...WELCOME_BASE,
  content:
    "Hi, I'm your AI writing assistant. Tell me your video script ideas or questions, and I'll help you outline, draft, and polish them."
};

type CoordinatorChatProps = {
  open: boolean;
  onClose: () => void;
  onClearQuote?: () => void;
  userInitial?: string;
  selectedText?: string;
  selectedRowId?: string;
  selectedColumnId?: string;
  projectId?: string;
  userId?: string;
  scriptVersionId?: string | null;
  mode?: "full" | "vanilla";
};

export function CoordinatorChat({
  open,
  onClose,
  onClearQuote,
  userInitial = "U",
  selectedText,
  selectedRowId,
  selectedColumnId,
  projectId,
  userId,
  scriptVersionId,
  mode = "full"
}: CoordinatorChatProps) {
  const isVanilla = mode === "vanilla";
  const welcome = isVanilla ? WELCOME_VANILLA : WELCOME_FULL;
  const setProject = useAppStore((state) => state.setProject);
  const [tab, setTab] = useState<AssistantTab>("chat");
  const [messages, setMessages] = useState<CoordinatorMessage[]>([welcome]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && selectedText) setTab("chat");
  }, [open, selectedText]);

  useEffect(() => {
    if (!open || !projectId || !userId) return;
    fetchCoordinatorMessages(projectId, userId)
      .then((loaded) => {
        if (loaded.length === 0) {
          setMessages([welcome]);
          return;
        }
        setMessages(loaded);
      })
      .catch(() => setMessages([welcome]));
  }, [open, projectId, userId, welcome]);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming]);

  if (!open) return null;

  async function handleSend() {
    const text = draft.trim();
    if (!text || streaming || !projectId || !userId) return;

    const quotes =
      selectedText && selectedText.trim()
        ? [
            {
              text: selectedText.trim(),
              row_id: selectedRowId,
              column_id: selectedColumnId,
              script_version_id: scriptVersionId ?? undefined
            }
          ]
        : [];

    const taskType = isVanilla ? "user_message" : resolveCoordinatorTaskType(text, { hasQuotes: quotes.length > 0 });

    const userMessage: CoordinatorMessage = {
      message_id: `local-user-${Date.now()}`,
      project_id: projectId,
      user_id: userId,
      role: "user",
      content: text,
      task_type: taskType,
      requested_perspectives: ["comprehensive"],
      quotes,
      related_node_ids: [],
      generated_artifact_ids: [],
      created_at: new Date().toISOString()
    };

    const assistantPlaceholder: CoordinatorMessage = {
      message_id: `local-assistant-${Date.now()}`,
      project_id: projectId,
      user_id: userId,
      role: "assistant",
      content: "",
      task_type: userMessage.task_type,
      requested_perspectives: ["comprehensive"],
      quotes,
      related_node_ids: [],
      generated_artifact_ids: [],
      created_at: new Date().toISOString()
    };

    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
    setDraft("");
    setTab(taskType === "generate_modification_schemes" ? "plans" : "chat");
    setStreaming(true);
    setStreamError(null);

    try {
      await streamCoordinatorMessage(
        projectId,
        userId,
        {
          message: text,
          task_type: taskType,
          requested_perspectives: ["comprehensive"],
          quotes,
          changed_row_ids: selectedRowId ? [selectedRowId] : [],
          mode
        },
        (event) => {
          if (event.type === "token") {
            setMessages((prev) =>
              prev.map((item) =>
                item.message_id === assistantPlaceholder.message_id
                  ? { ...item, content: item.content + event.content }
                  : item
              )
            );
          }
          if (event.type === "artifact") {
            const current = useAppStore.getState().project;
            if (current) {
              let next = current;
              if (event.rationale_nodes?.length) {
                const existingIds = new Set((current.rationale_nodes ?? []).map((node) => node.node_id));
                const mergedNodes = [
                  ...(current.rationale_nodes ?? []),
                  ...event.rationale_nodes.filter((node) => !existingIds.has(node.node_id))
                ];
                const existingEdgeIds = new Set((current.rationale_edges ?? []).map((edge) => edge.edge_id));
                const mergedEdges = [
                  ...(current.rationale_edges ?? []),
                  ...(event.rationale_edges ?? []).filter((edge) => !existingEdgeIds.has(edge.edge_id))
                ];
                next = { ...next, rationale_nodes: mergedNodes, rationale_edges: mergedEdges };
              }
              if (event.modification_schemes) {
                next = {
                  ...next,
                  modification_schemes: event.modification_schemes.slice(-1),
                  stale: { ...next.stale, modification_schemes: "up_to_date" }
                };
                setTab("plans");
                const focusId =
                  event.new_scheme_ids?.[event.new_scheme_ids.length - 1] ??
                  event.modification_schemes[event.modification_schemes.length - 1]?.scheme_id;
                if (focusId) {
                  const store = useAppStore.getState();
                  store.setEditorSchemeFocusId(focusId);
                  store.setWorkspaceView("editor");
                }
              }
              if (next !== current) setProject(next);
            }
            if (event.related_node_ids?.length) {
              setMessages((prev) =>
                prev.map((item) =>
                  item.message_id === assistantPlaceholder.message_id
                    ? { ...item, related_node_ids: event.related_node_ids ?? [] }
                    : item
                )
              );
            }
          }
          if (event.type === "done") {
            if (event.open_revision_proposals) setTab("plans");
            setMessages((prev) =>
              prev.map((item) =>
                item.message_id === assistantPlaceholder.message_id
                  ? {
                      ...item,
                      message_id: event.message_id || item.message_id,
                      generated_artifact_ids: event.generated_artifact_ids ?? item.generated_artifact_ids
                    }
                  : item
              )
            );
          }
          if (event.type === "error") {
            setStreamError(event.message);
          }
        }
      );
    } catch (error) {
      setStreamError(error instanceof Error ? error.message : "Coordinator stream failed");
    } finally {
      setStreaming(false);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  }

  return (
    <>
      <button className="glacier-backdrop" onClick={onClose} type="button" aria-label="Close Coordinator Chat" />
      <aside className="glacier-assistant" aria-label="Coordinator Agent Chat">
        <header className="glacier-header">
          <div className="glacier-header-top">
            <div className="glacier-title-row">
              <span className="glacier-icon-badge" aria-hidden="true">
                <IconLightning />
              </span>
              <span className="glacier-title">{isVanilla ? "AI Assistant" : "Coordinator Agent"}</span>
            </div>
            <button className="glacier-close" onClick={onClose} type="button" aria-label="Close">
              <IconClose />
            </button>
          </div>
          <div className="glacier-tabs" role="tablist" aria-label="Assistant views">
            <button
              className={`glacier-tab ${tab === "chat" ? "active" : ""}`}
              onClick={() => setTab("chat")}
              role="tab"
              aria-selected={tab === "chat"}
              type="button"
            >
              Chat
            </button>
            {/* <button
              className={`glacier-tab ${tab === "plans" ? "active" : ""}`}
              onClick={() => setTab("plans")}
              role="tab"
              aria-selected={tab === "plans"}
              type="button"
            >
              Revision Proposals
            </button> */}
          </div>
        </header>

        {tab === "plans" ? (
          <>
            <div className="glacier-body app-scrollbar">
              <RevisionProposalsList />
            </div>
            <RevisionProposalsActions />
          </>
        ) : (
          <div className="glacier-body app-scrollbar">
            {tab === "chat" ? (
              <div className="glacier-chat-thread" ref={threadRef} role="log" aria-live="polite">
                {messages.map((message) =>
                  message.role === "assistant" ? (
                    <div className="glacier-msg-row glacier-msg-row--assistant" key={message.message_id}>
                      <span className="glacier-avatar glacier-avatar--bot" aria-hidden="true">
                        <IconSpark />
                      </span>
                      <div className="glacier-bubble glacier-bubble--assistant">
                        {message.content || (streaming ? "…" : "")}
                        {message.related_node_ids.length > 0 ? (
                          <p className="glacier-related-nodes">
                            Related nodes: {message.related_node_ids.join(", ")}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  ) : (
                    <div className="glacier-msg-row glacier-msg-row--user" key={message.message_id}>
                      <div className="glacier-bubble glacier-bubble--user">{message.content}</div>
                      <span className="glacier-avatar glacier-avatar--user" aria-hidden="true">
                        {userInitial}
                      </span>
                    </div>
                  )
                )}
                {streamError ? <p className="glacier-stream-error">{streamError}</p> : null}
              </div>
            ) : (
              <div className="glacier-plans-list">
                <p className="glacier-plans-placeholder">Open a project to view revision proposals.</p>
              </div>
            )}
          </div>
        )}

        <footer className="glacier-input-area">
          {selectedText ? (
            <div className="glacier-quote">
              <span className="glacier-quote-icon" aria-hidden="true">
                ↳
              </span>
              <span className="glacier-quote-text">{selectedText}</span>
              <button
                className="glacier-quote-clear"
                onClick={onClearQuote}
                type="button"
                aria-label="Remove quote"
              >
                <IconClose />
              </button>
            </div>
          ) : null}
          <div className="glacier-input-wrap">
            <textarea
              className="glacier-input"
              placeholder={isVanilla ? "Ask the assistant…" : "Ask Coordinator…"}
              rows={1}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              aria-label="Coordinator message input"
              disabled={streaming}
            />
            <button className="glacier-send" onClick={() => void handleSend()} type="button" aria-label="Send" disabled={streaming}>
              <IconSend />
            </button>
          </div>
        </footer>
      </aside>
    </>
  );
}

function IconLightning() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function IconSpark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function IconSend() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}
