"use client";

import { useState } from "react";

type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  text: string;
};

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    text: "你好，我是 Coordinator Agent。你可以就脚本与节点图向我提问；品牌 / 观众 / 专家视角会在后台按需调度（Phase 2 接入真实 LLM）。"
  }
];

type CoordinatorChatProps = {
  open: boolean;
  onClose: () => void;
  userInitial?: string;
  selectedText?: string;
};

export function CoordinatorChat({ open, onClose, userInitial = "U", selectedText }: CoordinatorChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [draft, setDraft] = useState("");

  if (!open) return null;

  function handleSend() {
    const text = draft.trim();
    if (!text) return;

    const userMessage: ChatMessage = { id: `user-${Date.now()}`, role: "user", text };
    setMessages((prev) => [...prev, userMessage]);
    setDraft("");

    const contextHint = selectedText ? `（已引用脚本片段：「${selectedText.slice(0, 80)}${selectedText.length > 80 ? "…" : ""}」）` : "";
    window.setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          text: `收到你的问题。${contextHint} Phase 0 为 mock 回复；Phase 3 将通过 SSE 接入 Coordinator 与多视角分析。`
        }
      ]);
    }, 400);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  return (
    <>
      <button className="glacier-backdrop" onClick={onClose} type="button" aria-label="关闭 Coordinator Chat" />
      <aside className="glacier-assistant" aria-label="Coordinator Agent Chat">
        <header className="glacier-header">
          <div className="glacier-header-top">
            <div className="glacier-title-row">
              <span className="glacier-icon-badge" aria-hidden="true">
                <IconLightning />
              </span>
              <span className="glacier-title">Coordinator Agent</span>
            </div>
            <button className="glacier-close" onClick={onClose} type="button" aria-label="关闭">
              <IconClose />
            </button>
          </div>
        </header>

        <div className="glacier-body">
          <div className="glacier-chat-thread" role="log" aria-live="polite">
            {messages.map((message) =>
              message.role === "assistant" ? (
                <div className="glacier-msg-row glacier-msg-row--assistant" key={message.id}>
                  <span className="glacier-avatar glacier-avatar--bot" aria-hidden="true">
                    <IconSpark />
                  </span>
                  <div className="glacier-bubble glacier-bubble--assistant">{message.text}</div>
                </div>
              ) : (
                <div className="glacier-msg-row glacier-msg-row--user" key={message.id}>
                  <div className="glacier-bubble glacier-bubble--user">{message.text}</div>
                  <span className="glacier-avatar glacier-avatar--user" aria-hidden="true">
                    {userInitial}
                  </span>
                </div>
              )
            )}
          </div>
        </div>

        <footer className="glacier-input-area">
          {selectedText ? (
            <div className="glacier-quote">
              <span className="glacier-quote-icon" aria-hidden="true">
                ↳
              </span>
              <span className="glacier-quote-text">{selectedText}</span>
            </div>
          ) : null}
          <div className="glacier-input-wrap">
            <textarea
              className="glacier-input"
              placeholder="向 Coordinator 提问…"
              rows={1}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              aria-label="Coordinator 消息输入"
            />
            <button className="glacier-send" onClick={handleSend} type="button" aria-label="发送">
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
