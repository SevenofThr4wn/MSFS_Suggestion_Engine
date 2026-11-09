
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// ============================================================
// SHADCN / TAILWIND UTILITIES
// ============================================================

/**
 * Combines class names and resolves conflicting Tailwind classes.
 *
 * Example:
 * cn("bg-red-500", "bg-blue-500")
 * -> "bg-blue-500"
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

// ============================================================
// AIRPORT UTILITIES
// ============================================================

/**
 * Normalises an airport code by trimming whitespace
 * and converting it to uppercase.
 */
export function normaliseAirportCode(
  value: string | null | undefined,
): string {
  return (value ?? "").trim().toUpperCase();
}

// ============================================================
// NUMBER UTILITIES
// ============================================================

/**
 * Returns a finite number or a fallback.
 *
 * Prevents NaN and Infinity from appearing in the UI.
 */
export function finite(
  value: number | null | undefined,
  fallback = 0,
): number {
  if (typeof value !== "number") {
    return fallback;
  }

  return Number.isFinite(value) ? value : fallback;
}

/**
 * Formats flight duration from minutes.
 *
 * Examples:
 * 45  -> "45m"
 * 90  -> "1h 30m"
 * 120 -> "2h"
 * 185 -> "3h 5m"
 */
export function formatDuration(
  minutes: number | null | undefined,
): string {
  const totalMinutes = Math.max(
    0,
    Math.round(finite(minutes)),
  );

  const hours = Math.floor(totalMinutes / 60);
  const remainingMinutes = totalMinutes % 60;

  if (hours === 0) {
    return `${remainingMinutes}m`;
  }

  if (remainingMinutes === 0) {
    return `${hours}h`;
  }

  return `${hours}h ${remainingMinutes}m`;
}

// ============================================================
// FLIGHT STATUS UTILITIES
// ============================================================

const STATUS_LABELS: Record<string, string> = {
  pass: "Pass",
  valid: "Valid",
  suitable: "Suitable",

  indeterminate: "Indeterminate",
  unknown: "Unknown",
  pending: "Pending",

  fail: "Failed",
  failed: "Failed",
  unsuitable: "Unsuitable",

  warning: "Warning",
  caution: "Caution",
};

/**
 * Converts backend status codes into readable labels.
 *
 * Example:
 * "preliminary_pass" -> "Preliminary pass"
 */
export function statusLabel(
  status: string | null | undefined,
): string {
  if (!status) {
    return "Unknown";
  }

  const normalised = status.trim().toLowerCase();

  if (STATUS_LABELS[normalised]) {
    return STATUS_LABELS[normalised];
  }

  return normalised
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

// ============================================================
// ERROR UTILITIES
// ============================================================

/**
 * Converts unknown errors into readable strings.
 *
 * Compatible with Error objects, strings,
 * and API error responses containing a message.
 */
export function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  if (error && typeof error === "object") {
    const object = error as Record<string, unknown>;

    if (typeof object.detail === "string") {
      return object.detail;
    }

    if (typeof object.message === "string") {
      return object.message;
    }
  }

  return "An unexpected error occurred.";
}


/**
 * Safely serialise data for expandable diagnostic panels.
 */
export function pretty(value: unknown): string {
  try {
    const result = JSON.stringify(value, null, 2);
    return result ?? "No data available.";
  } catch {
    return "Unable to serialise diagnostic data.";
  }
}

/**
 * Restrict a score to the 0–100 range.
 */
export function clampScore(
  score: number | null | undefined,
): number {
  if (
    typeof score !== "number" ||
    !Number.isFinite(score)
  ) {
    return 0;
  }

  return Math.max(0, Math.min(100, score));
}

/**
 * Determine the colour category for a score ring.
 */
export function scoreClass(
  score: number | null | undefined,
): "high" | "medium" | "low" {
  const value = clampScore(score);

  if (value >= 80) return "high";
  if (value >= 50) return "medium";

  return "low";
}
