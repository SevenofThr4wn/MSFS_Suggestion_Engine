import type {
  AirportCoordinateLookup,
  AirportCoordinateResponse,
  RouteMapAirport,
  RouteMapCoordinates,
} from "@/lib/types/route_finder";

import type { ScoredRecommendation } from "@/lib/types/recommendation";

// ============================================================
// Coordinate API
// ============================================================

export async function fetchAirportCoordinates(
  codes: string[],
  signal?: AbortSignal,
): Promise<AirportCoordinateLookup> {
  const unique = [
    ...new Set(codes.map((code) => code.trim().toUpperCase())),
  ].sort();

  if (unique.length === 0) {
    return {};
  }

  const lookup: AirportCoordinateLookup = {};

  // The airport API supports up to 100 ICAO codes
  // per request.
  for (let offset = 0; offset < unique.length; offset += 100) {
    const batch = unique.slice(offset, offset + 100);

    const params = new URLSearchParams({
      codes: batch.join(","),
    });

    const response = await fetch(`/api/route_finder/airports?${params}`, {
      signal,
    });

    if (!response.ok) {
      throw new Error(`Airport lookup failed (${response.status}).`);
    }

    const data = (await response.json()) as AirportCoordinateResponse;

    if (!Array.isArray(data.airports)) {
      throw new Error("Invalid airport lookup response.");
    }

    for (const airport of data.airports) {
      if (
        /^[A-Z]{4}$/.test(airport.icao) &&
        Number.isFinite(airport.latitude) &&
        Number.isFinite(airport.longitude) &&
        Math.abs(airport.latitude) <= 90 &&
        Math.abs(airport.longitude) <= 180
      ) {
        lookup[airport.icao] = airport;
      }
    }
  }

  return lookup;
}

export function getRouteCoordinates(
  route: ScoredRecommendation,
  airports: AirportCoordinateLookup,
): RouteMapCoordinates | null {
  const departure = airports[route.route.departure_icao];

  const arrival = airports[route.route.arrival_icao];

  if (!departure || !arrival) {
    return null;
  }

  return { departure, arrival };
}

// ============================================================
// Geographic Helpers
// ============================================================

export type MapPosition = [number, number];

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

function toVector([longitude, latitude]: MapPosition): [
  number,
  number,
  number,
] {
  const lat = latitude * RAD;
  const lon = longitude * RAD;

  return [
    Math.cos(lat) * Math.cos(lon),
    Math.cos(lat) * Math.sin(lon),
    Math.sin(lat),
  ];
}

function toPosition([x, y, z]: [number, number, number]): MapPosition {
  return [Math.atan2(y, x) * DEG, Math.atan2(z, Math.hypot(x, y)) * DEG];
}

function normalizeLongitude(value: number): number {
  return ((((value + 180) % 360) + 360) % 360) - 180;
}

/**
 * Interpolate a great-circle path using spherical
 * linear interpolation.
 */
export function greatCirclePoints(
  departure: MapPosition,
  arrival: MapPosition,
  segments = 96,
): MapPosition[] {
  const a = toVector(departure);
  const b = toVector(arrival);

  const dot = Math.max(
    -1,
    Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]),
  );

  const angle = Math.acos(dot);
  const sine = Math.sin(angle);

  const points: MapPosition[] = [];

  // Deterministic orthogonal direction for antipodal
  // endpoints, where the shortest path is ambiguous.
  const cross: [number, number, number] =
    Math.abs(a[2]) < 0.9 ? [-a[1], a[0], 0] : [0, -a[2], a[1]];

  const norm = Math.hypot(...cross);

  const orthogonal: [number, number, number] = [
    cross[0] / norm,
    cross[1] / norm,
    cross[2] / norm,
  ];

  for (let i = 0; i <= segments; i++) {
    const t = i / segments;

    let vector: [number, number, number];

    if (angle < 1e-8) {
      vector = a;
    } else if (Math.abs(sine) < 1e-8) {
      vector = [
        Math.cos(Math.PI * t) * a[0] + Math.sin(Math.PI * t) * orthogonal[0],
        Math.cos(Math.PI * t) * a[1] + Math.sin(Math.PI * t) * orthogonal[1],
        Math.cos(Math.PI * t) * a[2] + Math.sin(Math.PI * t) * orthogonal[2],
      ];
    } else {
      const weightA = Math.sin((1 - t) * angle) / sine;

      const weightB = Math.sin(t * angle) / sine;

      vector = [
        weightA * a[0] + weightB * b[0],
        weightA * a[1] + weightB * b[1],
        weightA * a[2] + weightB * b[2],
      ];
    }

    points.push(toPosition(vector));
  }

  return points;
}

/**
 * Split a route into separate lines when it crosses
 * the International Date Line.
 */
export function splitAtDateLine(points: MapPosition[]): MapPosition[][] {
  if (points.length === 0) {
    return [];
  }

  const lines: MapPosition[][] = [];
  let current: MapPosition[] = [
    [normalizeLongitude(points[0][0]), points[0][1]],
  ];

  for (let i = 1; i < points.length; i++) {
    const previous = current[current.length - 1];

    const next: MapPosition = [normalizeLongitude(points[i][0]), points[i][1]];

    const difference = next[0] - previous[0];

    if (Math.abs(difference) <= 180) {
      current.push(next);
      continue;
    }

    const unwrappedLongitude = next[0] + (difference > 0 ? -360 : 360);

    const boundary = unwrappedLongitude > 180 ? 180 : -180;

    const fraction =
      (boundary - previous[0]) / (unwrappedLongitude - previous[0]);

    const latitude = previous[1] + fraction * (next[1] - previous[1]);

    current.push([boundary, latitude]);

    if (current.length >= 2) {
      lines.push(current);
    }

    current = [[-boundary, latitude], next];
  }

  if (current.length >= 2) {
    lines.push(current);
  }

  return lines;
}

/**
 * Produce a GeoJSON-compatible MultiLineString
 * for rendering a great-circle route.
 */
export function buildRouteGeometry(
  departure: RouteMapAirport,
  arrival: RouteMapAirport,
) {
  const points = greatCirclePoints(
    [departure.longitude, departure.latitude],
    [arrival.longitude, arrival.latitude],
  );

  return {
    type: "MultiLineString" as const,
    coordinates: splitAtDateLine(points),
  };
}

/**
 * Create bounds for a route, using unwrapped longitudes
 * to avoid fitting the entire world on date-line routes.
 */
export function routeBounds(
  departure: RouteMapAirport,
  arrival: RouteMapAirport,
): [MapPosition, MapPosition] {
  const points = greatCirclePoints(
    [departure.longitude, departure.latitude],
    [arrival.longitude, arrival.latitude],
  );

  const unwrapped: MapPosition[] = [];

  for (const point of points) {
    if (unwrapped.length === 0) {
      unwrapped.push(point);
      continue;
    }

    const last = unwrapped[unwrapped.length - 1][0];

    unwrapped.push([
      point[0] + 360 * Math.round((last - point[0]) / 360),
      point[1],
    ]);
  }

  return [
    [
      Math.min(...unwrapped.map((p) => p[0])),
      Math.min(...unwrapped.map((p) => p[1])),
    ],
    [
      Math.max(...unwrapped.map((p) => p[0])),
      Math.max(...unwrapped.map((p) => p[1])),
    ],
  ];
}
