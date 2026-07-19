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
 * Smooth progress from discrete backend step/total events.
 *
 * Between backend events, the percentage auto-advances slowly so the bar
 * never freezes. When a new step arrives, the display catches up smoothly.
 *
 * @param step   Current step from backend (1-based). 0 = not started.
 * @param total  Total number of steps.
 * @param active Whether the operation is in progress.
 * @returns A smoothly animated progress value (0–100).
 */
export function useSmoothProgress(
  step: number,
  total: number,
  active: boolean
): number {
  const [display, setDisplay] = useState(0);
  const targetRef = useRef(0);
  const autoRef = useRef(0);
  const lastStepRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!active || total <= 0) {
      setDisplay(0);
      targetRef.current = 0;
      autoRef.current = 0;
      lastStepRef.current = 0;
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    // Reset auto-advance when step changes
    if (step !== lastStepRef.current && step > 0) {
      lastStepRef.current = step;
      autoRef.current = 0;
    }

    // Update target: current step base + auto-advance, capped at the next step boundary
    const autoMax = step >= total ? 1.0 : 0.92; // last step can reach 100%
    const base = step > 0 ? (step - 1) / total : 0;
    const auto = autoRef.current / total;
    targetRef.current = Math.min(base + auto, (step / total) * autoMax) * 100;

    // Smoothly approach target every 100ms
    timerRef.current = setInterval(() => {
      // Auto-advance creeps forward (faster in early stages, slower near target)
      autoRef.current += 0.012;

      const autoMax2 = lastStepRef.current >= total ? 1.0 : 0.92;
      const base2 = lastStepRef.current > 0 ? (lastStepRef.current - 1) / total : 0;
      const auto2 = autoRef.current / total;
      const rawTarget = Math.min(base2 + auto2, (lastStepRef.current / total) * autoMax2) * 100;
      targetRef.current = Math.min(rawTarget, 100);

      // Lerp display toward target
      setDisplay((prev) => {
        const diff = targetRef.current - prev;
        if (Math.abs(diff) < 0.3) return targetRef.current;
        return prev + diff * 0.15;
      });
    }, 100);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [active, step, total]);

  return display;
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
