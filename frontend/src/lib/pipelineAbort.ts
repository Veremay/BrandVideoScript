/** Module-level abort controllers for long-running SSE pipelines (not serializable in UI state). */

let mapSyncController: AbortController | null = null;
let schemeGenController: AbortController | null = null;

export function beginMapSyncAbortSignal(): AbortSignal {
  mapSyncController?.abort();
  mapSyncController = new AbortController();
  return mapSyncController.signal;
}

export function getMapSyncAbortSignal(): AbortSignal | undefined {
  return mapSyncController?.signal;
}

export function abortMapSyncPipeline(): void {
  mapSyncController?.abort();
  mapSyncController = null;
}

export function clearMapSyncAbortController(): void {
  mapSyncController = null;
}

export function beginSchemeGenAbortSignal(): AbortSignal {
  schemeGenController?.abort();
  schemeGenController = new AbortController();
  return schemeGenController.signal;
}

export function getSchemeGenAbortSignal(): AbortSignal | undefined {
  return schemeGenController?.signal;
}

export function abortSchemeGenPipeline(): void {
  schemeGenController?.abort();
  schemeGenController = null;
}

export function clearSchemeGenAbortController(): void {
  schemeGenController = null;
}

export class PipelineCancelledError extends Error {
  constructor(message = "Cancelled") {
    super(message);
    this.name = "PipelineCancelledError";
  }
}

export function isPipelineCancelledError(error: unknown): boolean {
  return error instanceof PipelineCancelledError || (error instanceof Error && error.name === "PipelineCancelledError");
}
