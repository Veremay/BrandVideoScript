"use client";

import { useEffect, useRef, useState } from "react";

import { CoordinatorMarkdown } from "@/components/CoordinatorMarkdown";
import { RevisionProposalsActions, RevisionProposalsList } from "@/components/RevisionProposalsPanel";
import { fetchCoordinatorMessages, streamCoordinatorMessage } from "@/lib/api";
import { resolveCoordinatorTaskType } from "@/lib/coordinatorIntent";
import { normalizeProject } from "@/lib/normalizeProject";
import type { CoordinatorAttachment, CoordinatorMessage } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

type AssistantTab = "chat" | "plans";

const MAX_ATTACHMENTS = 3;
const MAX_ATTACHMENT_BYTES = 262_144;
const MAX_ATTACHMENT_CHARS = 20_000;
const VANILLA_SETUP_QUICK_REPLIES = ["Help me analyze brand requirements"] as const;
const VANILLA_EDITOR_QUICK_REPLIES = ["Help me analyze potential conflicts"] as const;
const SUPPORTED_ATTACHMENT_EXTENSIONS = new Set([
  "txt", "md", "markdown", "csv", "json", "xml", "yaml", "yml", "srt", "vtt",
  "html", "css", "js", "jsx", "ts", "tsx", "py"
]);

function isSupportedTextFile(file: File) {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return file.type.startsWith("text/") || SUPPORTED_ATTACHMENT_EXTENSIONS.has(extension);
}

function dragContainsUnsupportedFiles(dataTransfer: DataTransfer) {
  const files = Array.from(dataTransfer.items)
    .filter((item) => item.kind === "file")
    .map((item) => item.getAsFile())
    .filter((file): file is File => file !== null);
  return files.length > 0 && files.some((file) => !isSupportedTextFile(file));
}

function formatAttachmentSize(size: number) {
  return size < 1024 ? `${size} B` : `${Math.ceil(size / 1024)} KB`;
}

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
  embedded?: boolean;
  initialDraft?: string;
  messageTag?: string;
};

function taggedMessagePrefix(tag: string) {
  return `[VANILLA_SETUP:${tag}]`;
}

function visibleMessageContent(content: string) {
  return content.replace(/^\[VANILLA_SETUP:[A-Z_]+\]\s*/, "");
}

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
  mode = "full",
  embedded = false,
  initialDraft,
  messageTag
}: CoordinatorChatProps) {
  const isVanilla = mode === "vanilla";
  const welcome = isVanilla ? WELCOME_VANILLA : WELCOME_FULL;
  const setProject = useAppStore((state) => state.setProject);
  const pendingChatDraft = useAppStore((state) => state.pendingChatDraft);
  const setPendingChatDraft = useAppStore((state) => state.setPendingChatDraft);
  const docked = useAppStore((state) => state.layout.coordinatorChatDocked);
  const setCoordinatorChatDocked = useAppStore((state) => state.setCoordinatorChatDocked);
  const [tab, setTab] = useState<AssistantTab>("chat");
  const [messages, setMessages] = useState<CoordinatorMessage[]>([welcome]);
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<CoordinatorAttachment[]>([]);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [attachmentDragActive, setAttachmentDragActive] = useState(false);
  const [attachmentDragUnsupported, setAttachmentDragUnsupported] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const attachmentInputRef = useRef<HTMLInputElement>(null);
  const attachmentDragDepthRef = useRef(0);

  useEffect(() => {
    if (open && selectedText) setTab("chat");
  }, [open, selectedText]);

  useEffect(() => {
    if (!open || pendingChatDraft == null) return;
    setDraft((current) => {
      const existing = current.trim();
      if (existing) {
        return `${existing}\n\n${pendingChatDraft.appendBlock}`;
      }
      return pendingChatDraft.prompt;
    });
    setTab("chat");
    setPendingChatDraft(null);
  }, [open, pendingChatDraft, setPendingChatDraft]);

  useEffect(() => {
    if (!open || !initialDraft) return;
    setDraft(initialDraft);
  }, [open, initialDraft]);

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

  async function addAttachmentFiles(files: File[]) {
    if (!files.length) return;

    const availableSlots = MAX_ATTACHMENTS - attachments.length;
    if (availableSlots <= 0) {
      setAttachmentError(`You can attach up to ${MAX_ATTACHMENTS} files.`);
      return;
    }

    const nextAttachments: CoordinatorAttachment[] = [];
    let validationError: string | null = null;
    for (const file of files.slice(0, availableSlots)) {
      if (!isSupportedTextFile(file)) {
        validationError = `${file.name} is not supported. Upload a text, Markdown, CSV, JSON, subtitle, or code file.`;
        continue;
      }
      if (file.size > MAX_ATTACHMENT_BYTES) {
        validationError = `${file.name} exceeds the 256 KB limit.`;
        continue;
      }
      const content = await file.text();
      if (!content.trim()) {
        validationError = `${file.name} is empty.`;
        continue;
      }
      if (content.length > MAX_ATTACHMENT_CHARS) {
        validationError = `${file.name} exceeds the 20,000 character limit.`;
        continue;
      }
      nextAttachments.push({
        filename: file.name,
        content,
        mime_type: file.type || "text/plain",
        size: file.size
      });
    }

    if (nextAttachments.length) {
      setAttachments((current) => [...current, ...nextAttachments].slice(0, MAX_ATTACHMENTS));
    }
    if (files.length > availableSlots) {
      validationError = `Only the first ${availableSlots} selected file${availableSlots === 1 ? "" : "s"} were attached.`;
    }
    setAttachmentError(validationError);
  }

  async function handleAttachmentFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    await addAttachmentFiles(files);
  }

  function handleAttachmentDragEnter(event: React.DragEvent<HTMLElement>) {
    if (!isVanilla || streaming || !event.dataTransfer.types.includes("Files")) return;
    event.preventDefault();
    attachmentDragDepthRef.current += 1;
    setAttachmentDragUnsupported(dragContainsUnsupportedFiles(event.dataTransfer));
    setAttachmentDragActive(true);
  }

  function handleAttachmentDragOver(event: React.DragEvent<HTMLElement>) {
    if (!isVanilla || streaming || !event.dataTransfer.types.includes("Files")) return;
    event.preventDefault();
    const unsupported = dragContainsUnsupportedFiles(event.dataTransfer);
    setAttachmentDragUnsupported(unsupported);
    event.dataTransfer.dropEffect = "copy";
  }

  function handleAttachmentDragLeave(event: React.DragEvent<HTMLElement>) {
    if (!isVanilla || !event.dataTransfer.types.includes("Files")) return;
    event.preventDefault();
    attachmentDragDepthRef.current = Math.max(0, attachmentDragDepthRef.current - 1);
    if (attachmentDragDepthRef.current === 0) {
      setAttachmentDragActive(false);
      setAttachmentDragUnsupported(false);
    }
  }

  function handleAttachmentDrop(event: React.DragEvent<HTMLElement>) {
    if (!isVanilla || streaming || !event.dataTransfer.types.includes("Files")) return;
    event.preventDefault();
    attachmentDragDepthRef.current = 0;
    setAttachmentDragActive(false);
    setAttachmentDragUnsupported(false);
    void addAttachmentFiles(Array.from(event.dataTransfer.files));
  }

  async function handleSend(overrideText?: string) {
    const text =
      (overrideText ?? draft).trim() || (attachments.length ? "Please review the attached file(s)." : "");
    if (!text || streaming || !projectId || !userId) return;
    const sentAttachments = attachments;
    const persistedText = messageTag ? `${taggedMessagePrefix(messageTag)}\n${text}` : text;

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
      attachments: sentAttachments,
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
    setAttachments([]);
    setAttachmentError(null);
    setTab(taskType === "generate_modification_schemes" ? "plans" : "chat");
    setStreaming(true);
    setStreamError(null);

    try {
      await streamCoordinatorMessage(
        projectId,
        userId,
        {
          message: persistedText,
          task_type: taskType,
          requested_perspectives: ["comprehensive"],
          quotes,
          attachments: sentAttachments,
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
            const retryHint = event.retryable ? " 请稍后重试。" : "";
            setStreamError(`${event.message}${retryHint}`);
            if (event.project) {
              setProject(normalizeProject(event.project));
            }
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
      {!embedded && !docked ? (
        <button className="glacier-backdrop" onClick={onClose} type="button" aria-label="Close Coordinator Chat" />
      ) : null}
      <aside
        className={`glacier-assistant${docked || embedded ? " glacier-assistant--docked" : ""}${embedded ? " glacier-assistant--embedded" : ""}`}
        aria-label="Coordinator Agent Chat"
        onDragEnter={handleAttachmentDragEnter}
        onDragLeave={handleAttachmentDragLeave}
        onDragOver={handleAttachmentDragOver}
        onDrop={handleAttachmentDrop}
      >
        {isVanilla && attachmentDragActive ? (
          <div
            className={`glacier-drop-overlay${attachmentDragUnsupported ? " glacier-drop-overlay--unsupported" : ""}`}
            aria-live="polite"
          >
            <span className="glacier-drop-icon">
              <IconAttachment />
            </span>
            <strong>{attachmentDragUnsupported ? "Unsupported file format" : "Release to upload files"}</strong>
            <span>
              {attachmentDragUnsupported
                ? "Use text, Markdown, CSV, JSON, subtitle, or code files"
                : `Up to ${MAX_ATTACHMENTS} supported text files`}
            </span>
          </div>
        ) : null}
        <header className="glacier-header">
          <div className="glacier-header-top">
            <div className="glacier-title-row">
              <span className="glacier-icon-badge" aria-hidden="true">
                <IconRobot />
              </span>
              <span className="glacier-title">{isVanilla ? "AI Assistant" : "Coordinator Agent"}</span>
            </div>
            {!embedded ? <div className="glacier-header-actions">
              <button
                className="glacier-close"
                onClick={() => setCoordinatorChatDocked(!docked)}
                type="button"
                aria-label={docked ? "Restore floating chat" : "Dock chat to right sidebar"}
                title={docked ? "Restore floating chat" : "Dock to right sidebar"}
              >
                {docked ? <IconRestore /> : <IconExpand />}
              </button>
              <button className="glacier-close" onClick={onClose} type="button" aria-label="Close">
                <IconClose />
              </button>
            </div> : null}
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
                {messages.map((message, index) => {
                  const isActiveStream =
                    streaming && message.role === "assistant" && index === messages.length - 1;

                  return message.role === "assistant" ? (
                    <div className="glacier-msg-row glacier-msg-row--assistant" key={message.message_id}>
                      <span className="glacier-avatar glacier-avatar--bot" aria-hidden="true">
                        <IconRobot />
                      </span>
                      <div className="glacier-bubble glacier-bubble--assistant">
                        {message.content ? (
                          <CoordinatorMarkdown content={message.content} isAnimating={isActiveStream} />
                        ) : isActiveStream ? (
                          "…"
                        ) : null}
                        {message.related_node_ids.length > 0 ? (
                          <p className="glacier-related-nodes">
                            Related nodes: {message.related_node_ids.join(", ")}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  ) : (
                    <div className="glacier-msg-row glacier-msg-row--user" key={message.message_id}>
                      <div className="glacier-bubble glacier-bubble--user">
                        <span>{visibleMessageContent(message.content)}</span>
                        {message.attachments?.length ? (
                          <span className="glacier-message-attachments">
                            {message.attachments.map((attachment, index) => (
                              <span className="glacier-message-attachment" key={`${attachment.filename}-${index}`}>
                                <IconAttachment />
                                {attachment.filename}
                              </span>
                            ))}
                          </span>
                        ) : null}
                      </div>
                      <span className="glacier-avatar glacier-avatar--user" aria-hidden="true">
                        {userInitial}
                      </span>
                    </div>
                  );
                })}
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
          {isVanilla && attachments.length ? (
            <div className="glacier-attachment-list" aria-label="Selected attachments">
              {attachments.map((attachment, index) => (
                <div className="glacier-attachment-chip" key={`${attachment.filename}-${index}`}>
                  <IconAttachment />
                  <span className="glacier-attachment-name">{attachment.filename}</span>
                  <span className="glacier-attachment-size">{formatAttachmentSize(attachment.size)}</span>
                  <button
                    aria-label={`Remove ${attachment.filename}`}
                    disabled={streaming}
                    onClick={() => setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                    type="button"
                  >
                    <IconClose />
                  </button>
                </div>
              ))}
            </div>
          ) : null}
          {isVanilla && attachmentError ? <p className="glacier-attachment-error">{attachmentError}</p> : null}
          {isVanilla ? (
            <div className="glacier-quick-replies" aria-label="Suggested prompts">
              {(embedded ? VANILLA_SETUP_QUICK_REPLIES : VANILLA_EDITOR_QUICK_REPLIES).map((reply) => (
                <button
                  className="glacier-quick-reply"
                  disabled={streaming}
                  key={reply}
                  onClick={() => void handleSend(reply)}
                  type="button"
                >
                  {reply}
                </button>
              ))}
            </div>
          ) : null}
          <div className="glacier-input-wrap">
            {isVanilla ? (
              <>
                <input
                  accept=".txt,.md,.markdown,.csv,.json,.xml,.yaml,.yml,.srt,.vtt,.html,.css,.js,.jsx,.ts,.tsx,.py,text/*"
                  hidden
                  multiple
                  onChange={(event) => void handleAttachmentFiles(event)}
                  ref={attachmentInputRef}
                  type="file"
                />
                <button
                  aria-label="Attach text files"
                  className="glacier-attach"
                  disabled={streaming || attachments.length >= MAX_ATTACHMENTS}
                  onClick={() => attachmentInputRef.current?.click()}
                  title="Attach text files"
                  type="button"
                >
                  <IconAttachment />
                </button>
              </>
            ) : null}
            <textarea
              className={`glacier-input${isVanilla ? " glacier-input--with-attachment" : ""}`}
              placeholder={isVanilla ? "Ask the assistant…" : "Ask Coordinator…"}
              rows={4}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              aria-label="Coordinator message input"
              disabled={streaming}
            />
            <button className="glacier-send" onClick={() => void handleSend()} type="button" aria-label="Send" disabled={streaming || (!draft.trim() && !attachments.length)}>
              <IconSend />
            </button>
          </div>
        </footer>
      </aside>
    </>
  );
}

function IconRobot() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="5" y="9" width="14" height="11" rx="2" />
      <path d="M12 3v3" />
      <circle cx="12" cy="3" r="1" fill="currentColor" stroke="none" />
      <circle cx="9" cy="14" r="1" fill="currentColor" stroke="none" />
      <circle cx="15" cy="14" r="1" fill="currentColor" stroke="none" />
      <path d="M9 18h6" />
      <path d="M3 13v3" />
      <path d="M21 13v3" />
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

function IconExpand() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="3" y="3" width="7" height="18" rx="1" />
      <rect x="12" y="3" width="9" height="18" rx="1" />
    </svg>
  );
}

function IconRestore() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="6" y="8" width="12" height="13" rx="1.5" />
      <path d="M9 8V6a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1h-2" />
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

function IconAttachment() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="m21.4 11.6-8.9 8.9a6 6 0 0 1-8.5-8.5l9.6-9.6a4 4 0 0 1 5.7 5.7l-9.6 9.6a2 2 0 0 1-2.8-2.8l8.9-8.9" />
    </svg>
  );
}
