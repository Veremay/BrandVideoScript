import type { SchemeGenProgress } from "@/store/appStore";

const SCHEME_GEN_STORAGE_KEY = "brandvideo:scheme-gen";

export type PersistedSchemeGen = {
  projectId: string;
  generating: boolean;
  progress: SchemeGenProgress | null;
};

export function readPersistedSchemeGen(): PersistedSchemeGen | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(SCHEME_GEN_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedSchemeGen;
    if (!parsed?.projectId || typeof parsed.generating !== "boolean") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function writePersistedSchemeGen(state: PersistedSchemeGen | null): void {
  if (typeof window === "undefined") return;
  try {
    if (!state?.generating || !state.projectId) {
      window.sessionStorage.removeItem(SCHEME_GEN_STORAGE_KEY);
      return;
    }
    window.sessionStorage.setItem(SCHEME_GEN_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore quota / private mode
  }
}

export function clearPersistedSchemeGen(): void {
  writePersistedSchemeGen(null);
}

/** Prefer known SSE progress; never invent a low fake percent after refresh. */
export function schemeGenPercentLabel(progress: SchemeGenProgress | null | undefined): string {
  if (progress && progress.total > 0) {
    const pct = Math.min(100, Math.round((progress.step / progress.total) * 100));
    return `Generating… ${pct}%`;
  }
  return "Generating…";
}

export function schemeGenPercentValue(progress: SchemeGenProgress | null | undefined): number {
  if (progress && progress.total > 0) {
    return Math.min(100, Math.round((progress.step / progress.total) * 100));
  }
  return 0;
}
