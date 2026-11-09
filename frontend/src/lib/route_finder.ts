import type {
  RecommendationResponse,
  ScoredRecommendation,
} from "@/lib/types/recommendation";

import type { RouteFinderFilters } from "@/lib/types/route_finder";

const RECOMMENDATIONS_ENDPOINT = "/api/recommendations/generate";


export function buildRouteFinderRequest(
  filters: RouteFinderFilters,
): Record<string, unknown> {
  return {
    mode: "discovery",

    departure_code: filters.departureCode.trim().toUpperCase(),

    arrival_code: filters.arrivalCode.trim().toUpperCase() || null,

    preferred_category: filters.aircraftCategory || null,

    airport_mode: filters.airportMode,

    min_duration_hours: filters.minDurationHours,
    max_duration_hours: filters.maxDurationHours,

    owned_only: filters.ownedOnly,

    prefer_addon_scenery: filters.preferAddonScenery,

    include_indeterminate: filters.includeIndeterminate,

    require_real_world_route: filters.requireRealWorldRoute,

    limit: filters.limit,
    max_candidates: 1000,

    live_weather: false,
    scenarios_enabled: false,

    include_decision_trace: false,
    include_rejected_examples: false,

    departure_gate_enabled: false,
  };
}

export function validateRouteFinderFilters(filters: RouteFinderFilters): void {
  if (!filters.departureCode.trim()) {
    throw new Error("A departure airport is required.");
  }

  if (
    !Number.isFinite(filters.minDurationHours) ||
    !Number.isFinite(filters.maxDurationHours) ||
    filters.minDurationHours <= 0 ||
    filters.maxDurationHours < filters.minDurationHours
  ) {
    throw new Error("Please provide a valid flight duration range.");
  }

  if (!Number.isInteger(filters.limit) || filters.limit < 1) {
    throw new Error("The recommendation limit must be a positive integer.");
  }
}

async function parseApiError(response: Response): Promise<string> {
  const fallback = `Recommendation request failed (${response.status}).`;

  try {
    const body: unknown = await response.json();

    if (typeof body === "object" && body !== null && "detail" in body) {
      const detail = body.detail;

      if (typeof detail === "string") {
        return detail;
      }

      if (Array.isArray(detail)) {
        return detail
          .map((issue: unknown) => {
            if (
              typeof issue === "object" &&
              issue !== null &&
              "msg" in issue &&
              typeof issue.msg === "string"
            ) {
              return issue.msg;
            }

            return String(issue);
          })
          .join("; ");
      }
    }

    return fallback;
  } catch {
    return fallback;
  }
}


export async function fetchRecommendations(
  filters: RouteFinderFilters,
  signal?: AbortSignal,
): Promise<RecommendationResponse> {
  validateRouteFinderFilters(filters);

  const response = await fetch(RECOMMENDATIONS_ENDPOINT, {
    method: "POST",

    headers: {
      "Content-Type": "application/json",
    },

    body: JSON.stringify(buildRouteFinderRequest(filters)),

    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const data: RecommendationResponse = await response.json();

  if (!Array.isArray(data.recommendations)) {
    throw new Error("The recommendation API returned an invalid response.");
  }

  return data;
}


export function routeKey(item: ScoredRecommendation): string {
  const route = item.route;

  return [
    route.route_id ?? "discovery",
    route.departure_icao,
    route.arrival_icao,
    route.aircraft_id,
    route.flight_number ?? "",
  ].join(":");
}

export function formatDuration(minutes: number): string {
  const roundedMinutes = Math.round(minutes);
  const hours = Math.floor(roundedMinutes / 60);
  const remaining = roundedMinutes % 60;

  return `${hours}h ${String(remaining).padStart(2, "0")}m`;
}

export function formatDistance(nauticalMiles: number): string {
  return `${Math.round(nauticalMiles).toLocaleString()} NM`;
}
