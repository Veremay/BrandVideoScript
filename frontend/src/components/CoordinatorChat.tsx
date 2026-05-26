"use client";

import { useEffect, useState } from "react";

type AssistantTab = "chat" | "plans";

type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  text: string;
};

type PlanItem = {
  id: string;
  title: string;
  description: string;
  active?: boolean;
};

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    text: "Hi, I'm the Coordinator Agent. Upload a Brief to run brand + expert initial parse; use Personas → From Analytics for audience nodes. Full streaming chat arrives in Phase 3."
  }
];

const PLANS: PlanItem[] = [
  {
    id: "a",
    title: "Plan A: Cinematic Expansion",
    description:
      "Adds two additional establishing shots and extends the ambient music pad to create a more immersive atmospheric opening.",
    active: true
  },
  {
    id: "b",
    title: "Plan B: Technical Efficiency",
    description:
      "Condenses the opening sequence into a single block to reduce production complexity while maintaining narrative impact."
  },
  {
    id: "c",
    title: "Plan C: Narrative Focus",
    description: "Introduces character voiceover earlier in scene 01 to establish the emotional core of the series immediately."
  }
];

type CoordinatorChatProps = {
  open: boolean;
  onClose: () => void;
  userInitial?: string;
  selectedText?: string;
};

export function CoordinatorChat({ open, onClose, userInitial = "U", selectedText }: CoordinatorChatProps) {
  const [tab, setTab] = useState<AssistantTab>("chat");
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [activePlanId, setActivePlanId] = useState("a");
  const [draft, setDraft] = useState("");

  useEffect(() => {
    if (open && selectedText) setTab("chat");
  }, [open, selectedText]);

  if (!open) return null;

  function handleSend() {
    const text = draft.trim();
    if (!text) return;

    const userMessage: ChatMessage = { id: `user-${Date.now()}`, role: "user", text };
    setMessages((prev) => [...prev, userMessage]);
    setDraft("");
    setTab("chat");

    const contextHint = selectedText
      ? ` (Quoted script: "${selectedText.slice(0, 80)}${selectedText.length > 80 ? "…" : ""}")`
      : "";
    window.setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          text: `Got your question.${contextHint} This is a mock reply in Phase 0; Phase 3 will stream Coordinator responses over SSE.`
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
      <button className="glacier-backdrop" onClick={onClose} type="button" aria-label="Close Coordinator Chat" />
      <aside className="glacier-assistant" aria-label="Coordinator Agent Chat">
        <header className="glacier-header">
          <div className="glacier-header-top">
            <div className="glacier-title-row">
              <span className="glacier-icon-badge" aria-hidden="true">
                <IconLightning />
              </span>
              <span className="glacier-title">Coordinator Agent</span>
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
            <button
              className={`glacier-tab ${tab === "plans" ? "active" : ""}`}
              onClick={() => setTab("plans")}
              role="tab"
              aria-selected={tab === "plans"}
              type="button"
            >
              Revision Proposals
            </button>
          </div>
        </header>

        <div className="glacier-body">
          {tab === "chat" ? (
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
          ) : (
            <div className="glacier-plans-list">
              {PLANS.map((plan) => {
                const isActive = plan.id === activePlanId;
                return (
                  <article
                    className={`glacier-plan-card ${isActive ? "glacier-plan-card--active" : ""}`}
                    key={plan.id}
                  >
                    <div className="glacier-plan-head">
                      <h3 className="glacier-plan-title">{plan.title}</h3>
                      {isActive ? <span className="glacier-plan-badge">ACTIVE</span> : null}
                    </div>
                    <p className="glacier-plan-desc">{plan.description}</p>
                    <button
                      className={`glacier-plan-btn ${isActive ? "glacier-plan-btn--active" : ""}`}
                      onClick={() => setActivePlanId(plan.id)}
                      type="button"
                    >
                      {isActive ? "Currently Previewing" : "Preview Plan"}
                    </button>
                  </article>
                );
              })}
            </div>
          )}
        </div>

        {tab === "plans" ? (
          <div className="glacier-plans-actions">
            <div className="glacier-plans-actions-row">
              <button className="glacier-btn glacier-btn--primary" type="button">
                Accept All
              </button>
              <button className="glacier-btn glacier-btn--outline" type="button">
                Accept Map Only
              </button>
            </div>
            <button className="glacier-reject-all" type="button">
              Reject All
            </button>
          </div>
        ) : null}

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
              placeholder="Ask Coordinator…"
              rows={1}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              aria-label="Coordinator message input"
            />
            <button className="glacier-send" onClick={handleSend} type="button" aria-label="Send">
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
