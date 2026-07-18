"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Returns the number of seconds since `active` became true.
 * Resets to 0 when `active` becomes false.
 */
export function useElapsedTime(active: boolean): number {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (active) {
      startRef.current = Date.now();
      setElapsed(0);
      intervalRef.current = setInterval(() => {
        if (startRef.current !== null) {
          setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
        }
      }, 250);
    } else {
      startRef.current = null;
      setElapsed(0);
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [active]);

  return elapsed;
}

/**
 * Format seconds into a compact human-readable string.
 * e.g. 5 → "5s", 75 → "1m 15s", 3661 → "1h 1m"
 */
export function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;

  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;

  if (mins < 60) {
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  }

  const hrs = Math.floor(mins / 60);
  const remainMin = mins % 60;
  return remainMin > 0 ? `${hrs}h ${remainMin}m` : `${hrs}h`;
}

/**
 * A thin animated indeterminate progress bar + elapsed time label.
 *
 * @param elapsed  Seconds since the operation started (from useElapsedTime).
 * @param label    Human-readable operation name, e.g. "Updating map".
 * @param inline   When true, renders bar + time in a horizontal row (compact).
 */
export function LoadingIndicator({
  elapsed,
  label,
  inline = false,
  progress
}: {
  elapsed: number;
  label: string;
  inline?: boolean;
  /** 0–100 determinate progress. When undefined, shows indeterminate animation instead. */
  progress?: number;
}) {
  const pct = progress != null ? Math.min(100, Math.max(0, Math.round(progress))) : undefined;

  return (
    <div className={`loading-progress${inline ? " loading-progress--inline" : ""}`}>
      {pct != null ? (
        <progress className="loading-progress-bar loading-progress-bar--determinate" value={pct} max={100} aria-label={label} />
      ) : (
        <div className="loading-progress-bar" role="progressbar" aria-label={label} aria-busy="true" />
      )}
      <span className="loading-progress-label">
        {label}… {formatElapsed(elapsed)}
      </span>
    </div>
  );
}
