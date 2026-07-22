/** Capture interactive clicks and batch-upload them to activity_logs. */

export type UiActivityAction = "ui.click" | "ui.keydown" | "ui.track";

export type UiActivityEventPayload = {
  action: UiActivityAction;
  client_ts: string;
  session_id: string;
  meta: Record<string, string | number | boolean>;
};

type TrackerContext = {
  projectId: string;
  userId: string;
  mode?: string;
  workspace?: string;
  upload: (projectId: string, userId: string, events: UiActivityEventPayload[]) => Promise<unknown>;
};

const FLUSH_INTERVAL_MS = 2000;
const FLUSH_SIZE = 20;
const MAX_QUEUE = 200;
const TEXT_MAX = 80;
const SESSION_STORAGE_KEY = "brandvideo:ui_session_id";

let queue: UiActivityEventPayload[] = [];
let flushTimer: number | null = null;
let context: TrackerContext | null = null;
let sessionId = "";
let attached = false;
let flushing = false;

function ensureSessionId(): string {
  if (sessionId) return sessionId;
  try {
    const stored = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (stored) {
      sessionId = stored;
      return sessionId;
    }
  } catch {
    // ignore storage failures
  }
  sessionId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID().slice(0, 12)
      : `s_${Date.now().toString(36)}`;
  try {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  } catch {
    // ignore
  }
  return sessionId;
}

function truncate(text: string, max = TEXT_MAX): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max)}…`;
}

function isIgnoredTarget(el: Element | null): boolean {
  if (!el) return true;
  if (el.closest("[data-ui-track-ignore]")) return true;
  const tag = el.tagName.toLowerCase();
  if (tag === "html" || tag === "body") return true;
  return false;
}

function findInteractive(el: Element | null): HTMLElement | null {
  if (!el) return null;
  const hit = el.closest(
    "[data-track], button, a, [role='button'], input[type='button'], input[type='submit'], summary"
  );
  return hit instanceof HTMLElement ? hit : null;
}

function classHint(el: HTMLElement): string {
  const classes = typeof el.className === "string" ? el.className.trim() : "";
  if (!classes) return el.tagName.toLowerCase();
  return truncate(`${el.tagName.toLowerCase()}.${classes.split(/\s+/).slice(0, 3).join(".")}`, 120);
}

function buildClickMeta(el: HTMLElement): Record<string, string | number | boolean> {
  const track = el.getAttribute("data-track")?.trim();
  const label =
    el.getAttribute("aria-label")?.trim() ||
    el.getAttribute("title")?.trim() ||
    truncate(el.innerText || el.textContent || "");
  const meta: Record<string, string | number | boolean> = {
    role: el.getAttribute("role") || el.tagName.toLowerCase(),
    hint: classHint(el)
  };
  if (track) meta.data_track = track;
  if (label) meta.target = label;
  if (el instanceof HTMLAnchorElement && el.href) meta.href = truncate(el.href, 160);
  if (context?.mode) meta.mode = context.mode;
  if (context?.workspace) meta.workspace = context.workspace;
  if (typeof window !== "undefined") meta.path = truncate(window.location.pathname, 120);
  return meta;
}

function scheduleFlush() {
  if (flushTimer !== null) return;
  flushTimer = window.setTimeout(() => {
    flushTimer = null;
    void flushQueue();
  }, FLUSH_INTERVAL_MS);
}

function enqueue(event: UiActivityEventPayload) {
  queue.push(event);
  if (queue.length > MAX_QUEUE) {
    queue = queue.slice(-MAX_QUEUE);
  }
  if (queue.length >= FLUSH_SIZE) {
    void flushQueue();
    return;
  }
  scheduleFlush();
}

async function flushQueue() {
  if (!context || flushing || queue.length === 0) return;
  flushing = true;
  const batch = queue.splice(0, FLUSH_SIZE);
  try {
    await context.upload(context.projectId, context.userId, batch);
  } catch {
    // Re-queue failed events (best effort); drop if queue is already full.
    queue = [...batch, ...queue].slice(0, MAX_QUEUE);
    scheduleFlush();
  } finally {
    flushing = false;
    if (queue.length >= FLUSH_SIZE) {
      void flushQueue();
    } else if (queue.length > 0) {
      scheduleFlush();
    }
  }
}

function flushWithBeacon() {
  if (!context || queue.length === 0) return;
  const batch = queue.splice(0, FLUSH_SIZE);
  const body = JSON.stringify({ user_id: context.userId, events: batch });
  const url = `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api"}/projects/${context.projectId}/activity-logs/batch`;
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      if (navigator.sendBeacon(url, blob)) return;
    }
  } catch {
    // fall through
  }
  // Best-effort keepalive fetch when beacon is unavailable.
  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true
  }).catch(() => {
    /* ignore unload failures */
  });
}

function onDocumentClick(event: MouseEvent) {
  if (!context) return;
  const rawTarget = event.target;
  if (!(rawTarget instanceof Element)) return;
  if (isIgnoredTarget(rawTarget)) return;

  const interactive = findInteractive(rawTarget);
  if (!interactive) return;
  if (interactive.closest("[data-ui-track-ignore]")) return;

  // Skip pure text fields (typing is not a click action we care about for buttons).
  const tag = interactive.tagName.toLowerCase();
  if (tag === "input") {
    const type = (interactive as HTMLInputElement).type || "text";
    if (!["button", "submit", "checkbox", "radio", "reset"].includes(type)) return;
  }

  enqueue({
    action: "ui.click",
    client_ts: new Date().toISOString(),
    session_id: ensureSessionId(),
    meta: buildClickMeta(interactive)
  });
}

function onVisibilityChange() {
  if (document.visibilityState === "hidden") {
    flushWithBeacon();
  }
}

function onPageHide() {
  flushWithBeacon();
}

/** Explicit semantic track (for non-DOM actions like hunk accept). */
export function trackUiEvent(
  dataTrack: string,
  meta: Record<string, string | number | boolean> = {}
) {
  if (!context) return;
  enqueue({
    action: "ui.track",
    client_ts: new Date().toISOString(),
    session_id: ensureSessionId(),
    meta: {
      data_track: dataTrack,
      ...(context.mode ? { mode: context.mode } : {}),
      ...(context.workspace ? { workspace: context.workspace } : {}),
      ...meta
    }
  });
}

export function startUiActivityTracker(next: TrackerContext) {
  context = next;
  ensureSessionId();
  if (attached) return;
  document.addEventListener("click", onDocumentClick, true);
  document.addEventListener("visibilitychange", onVisibilityChange);
  window.addEventListener("pagehide", onPageHide);
  attached = true;
}

export function updateUiActivityTrackerContext(
  patch: Partial<Pick<TrackerContext, "projectId" | "userId" | "mode" | "workspace">>
) {
  if (!context) return;
  context = { ...context, ...patch };
}

export function stopUiActivityTracker() {
  if (attached) {
    document.removeEventListener("click", onDocumentClick, true);
    document.removeEventListener("visibilitychange", onVisibilityChange);
    window.removeEventListener("pagehide", onPageHide);
    attached = false;
  }
  if (flushTimer !== null) {
    window.clearTimeout(flushTimer);
    flushTimer = null;
  }
  flushWithBeacon();
  context = null;
  queue = [];
}
