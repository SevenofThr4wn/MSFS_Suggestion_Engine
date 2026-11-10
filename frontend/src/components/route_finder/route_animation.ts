
export const ROUTE_ANIMATION = {
  durationMs: 7000,
  dashLength: 0.18,
  dashGap: 0.65,
  altitude: 0.16,
  selectedAltitude: 0.24,
  normalColor: "#d946ef",
  selectedColor: "#facc15",
  airportColor: "#facc15",
} as const;

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  return window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;
}

export function arcDashLength(selected: boolean): number {
  return selected
    ? ROUTE_ANIMATION.dashLength
    : ROUTE_ANIMATION.dashLength * 0.7;
}

export function arcDashGap(): number {
  return ROUTE_ANIMATION.dashGap;
}

export function arcDashAnimateTime(
  selected: boolean,
  reducedMotion: boolean,
): number {
  if (reducedMotion) return 0;

  return selected
    ? ROUTE_ANIMATION.durationMs
    : ROUTE_ANIMATION.durationMs * 1.5;
}
