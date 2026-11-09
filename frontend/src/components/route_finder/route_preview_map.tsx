"use client";

import { useEffect, useRef, useState } from "react";
import { MapPinned } from "lucide-react";

import "maplibre-gl/dist/maplibre-gl.css";

import type { RouteMapCoordinates } from "@/lib/types/route_finder";

interface RoutePreviewMapProps {
  coordinates?: RouteMapCoordinates | null;
  height?: number;
}

const DARK_MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

function toDegrees(radians: number): number {
  return (radians * 180) / Math.PI;
}

/**
 * Generate intermediate points along the shortest
 * great-circle path between two airports.
 */
function createGreatCircle(
  departure: [number, number],
  arrival: [number, number],
  segments = 96,
): [number, number][] {
  const lon1 = toRadians(departure[0]);
  const lat1 = toRadians(departure[1]);

  const lon2 = toRadians(arrival[0]);
  const lat2 = toRadians(arrival[1]);

  const a = [
    Math.cos(lat1) * Math.cos(lon1),
    Math.cos(lat1) * Math.sin(lon1),
    Math.sin(lat1),
  ];

  const b = [
    Math.cos(lat2) * Math.cos(lon2),
    Math.cos(lat2) * Math.sin(lon2),
    Math.sin(lat2),
  ];

  const dot = Math.max(
    -1,
    Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]),
  );

  const angle = Math.acos(dot);
  const sinAngle = Math.sin(angle);

  const points: [number, number][] = [];

  for (let i = 0; i <= segments; i++) {
    const t = i / segments;

    let x: number;
    let y: number;
    let z: number;

    if (angle < 1e-8) {
      x = a[0];
      y = a[1];
      z = a[2];
    } else if (Math.abs(sinAngle) < 1e-8) {
      // Antipodal airports have no unique shortest arc.
      // Use a deterministic orthogonal great-circle plane.
      let nx = -a[1];
      let ny = a[0];
      let nz = 0;

      const norm = Math.hypot(nx, ny, nz);

      if (norm < 1e-8) {
        nx = 1;
        ny = 0;
        nz = 0;
      } else {
        nx /= norm;
        ny /= norm;
        nz /= norm;
      }

      x = Math.cos(Math.PI * t) * a[0] + Math.sin(Math.PI * t) * nx;
      y = Math.cos(Math.PI * t) * a[1] + Math.sin(Math.PI * t) * ny;
      z = Math.cos(Math.PI * t) * a[2] + Math.sin(Math.PI * t) * nz;
    } else {
      const weightA = Math.sin((1 - t) * angle) / sinAngle;

      const weightB = Math.sin(t * angle) / sinAngle;

      x = weightA * a[0] + weightB * b[0];
      y = weightA * a[1] + weightB * b[1];
      z = weightA * a[2] + weightB * b[2];
    }

    const longitude = toDegrees(Math.atan2(y, x));
    const latitude = toDegrees(Math.atan2(z, Math.hypot(x, y)));

    // Unwrap longitudes to keep the route continuous
    // when crossing the international date line.
    if (points.length > 0) {
      const previous = points[points.length - 1][0];
      const shift = Math.round((previous - longitude) / 360);

      points.push([longitude + shift * 360, latitude]);
    } else {
      points.push([longitude, latitude]);
    }
  }

  return points;
}

function validCoordinates(
  coordinates: RouteMapCoordinates | null | undefined,
): coordinates is RouteMapCoordinates {
  if (!coordinates) {
    return false;
  }

  return [coordinates.departure, coordinates.arrival].every(
    (airport) =>
      Number.isFinite(airport.latitude) &&
      Number.isFinite(airport.longitude) &&
      Math.abs(airport.latitude) <= 90 &&
      Math.abs(airport.longitude) <= 180,
  );
}

export default function RoutePreviewMap({
  coordinates,
  height = 220,
}: RoutePreviewMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  const departureIcao = coordinates?.departure.icao;
  const arrivalIcao = coordinates?.arrival.icao;
  const departureLat = coordinates?.departure.latitude;
  const departureLon = coordinates?.departure.longitude;
  const arrivalLat = coordinates?.arrival.latitude;
  const arrivalLon = coordinates?.arrival.longitude;

  const hasCoordinates = validCoordinates(coordinates);

  useEffect(() => {
    if (!hasCoordinates || !containerRef.current) {
      return;
    }

    let cancelled = false;
    let mapInstance: import("maplibre-gl").Map | null = null;

    setError(null);

    async function initialize() {
      try {
        const maplibregl = await import("maplibre-gl");

        if (cancelled || !containerRef.current) {
          return;
        }

        const departure: [number, number] = [departureLon!, departureLat!];
        const arrival: [number, number] = [arrivalLon!, arrivalLat!];
        const path = createGreatCircle(departure, arrival);

        mapInstance = new maplibregl.Map({
          container: containerRef.current,
          style: DARK_MAP_STYLE,
          center: departure,
          zoom: 2,
          interactive: false,
          attributionControl: false,
        });

        const map = mapInstance;

        map.on("load", () => {
          if (cancelled) {
            return;
          }

          map.addSource("preview-route", {
            type: "geojson",
            data: {
              type: "Feature",
              geometry: {
                type: "LineString",
                coordinates: path,
              },
              properties: {},
            },
          });

          map.addLayer({
            id: "preview-route-line",
            type: "line",
            source: "preview-route",
            paint: {
              "line-color": "#d946ef",
              "line-width": 2.5,
              "line-opacity": 0.9,
            },
            layout: {
              "line-cap": "round",
              "line-join": "round",
            },
          });

          map.addSource("preview-airports", {
            type: "geojson",
            data: {
              type: "FeatureCollection",
              features: [
                {
                  type: "Feature",
                  properties: {
                    icao: departureIcao ?? "",
                  },
                  geometry: {
                    type: "Point",
                    coordinates: path[0],
                  },
                },
                {
                  type: "Feature",
                  properties: {
                    icao: arrivalIcao ?? "",
                  },
                  geometry: {
                    type: "Point",
                    coordinates: path[path.length - 1],
                  },
                },
              ],
            },
          });

          map.addLayer({
            id: "preview-airport-halo",
            type: "circle",
            source: "preview-airports",
            paint: {
              "circle-radius": 8,
              "circle-color": "#facc15",
              "circle-opacity": 0.15,
            },
          });

          map.addLayer({
            id: "preview-airport-points",
            type: "circle",
            source: "preview-airports",
            paint: {
              "circle-radius": 4,
              "circle-color": "#facc15",
              "circle-stroke-color": "#111217",
              "circle-stroke-width": 1.5,
            },
          });

          const longitudes = path.map((point) => point[0]);
          const latitudes = path.map((point) => point[1]);

          map.fitBounds(
            [
              [Math.min(...longitudes), Math.min(...latitudes)],
              [Math.max(...longitudes), Math.max(...latitudes)],
            ],
            {
              padding: 35,
              duration: 0,
              maxZoom: 6,
            },
          );
        });

        map.on("error", (event) => {
          if (!cancelled) {
            console.error("Route preview map error:", event.error);
            setError("Unable to load map tiles.");
          }
        });
      } catch (cause) {
        if (!cancelled) {
          console.error("Failed to initialize route preview:", cause);
          setError("Unable to initialize the route map.");
        }
      }
    }

    void initialize();

    return () => {
      cancelled = true;
      mapInstance?.remove();
    };
  }, [
    hasCoordinates,
    departureIcao,
    arrivalIcao,
    departureLat,
    departureLon,
    arrivalLat,
    arrivalLon,
  ]);

  if (!hasCoordinates) {
    return (
      <div
        style={{ height }}
        className="flex flex-col items-center justify-center gap-3 rounded-xl border border-white/[0.07] bg-[#17191f] px-6 text-center"
      >
        <MapPinned className="size-6 text-zinc-600" />

        <div>
          <p className="text-xs font-medium text-zinc-400">
            Route map unavailable
          </p>

          <p className="mt-1 text-[11px] leading-5 text-zinc-600">
            Airport coordinates have not been loaded.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{ height }}
      className="relative overflow-hidden rounded-xl border border-white/[0.07] bg-[#17191f]"
    >
      <div ref={containerRef} className="absolute inset-0" />

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#17191f]/95 px-5 text-center text-xs text-zinc-400">
          {error}
        </div>
      )}

      <div className="pointer-events-none absolute bottom-2 left-2 rounded-md bg-black/70 px-2 py-1 font-mono text-[10px] text-zinc-200">
        {departureIcao} → {arrivalIcao}
      </div>

      <div className="pointer-events-none absolute bottom-2 right-2 rounded-md bg-black/70 px-2 py-1 text-[9px] text-zinc-400">
        © OpenStreetMap © CARTO
      </div>
    </div>
  );
}
