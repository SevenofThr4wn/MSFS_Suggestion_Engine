"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { useQuery } from "@tanstack/react-query";

import {
  AlertCircle,
  LoaderCircle,
  Map as MapIcon,
  RefreshCw,
  Table2,
  X,
} from "lucide-react";

import "ol/ol.css";

import Map from "ol/Map";
import View from "ol/View";
import Feature from "ol/Feature";
import LineString from "ol/geom/LineString";
import Point from "ol/geom/Point";
import TileLayer from "ol/layer/Tile";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import XYZ from "ol/source/XYZ";
import { fromLonLat } from "ol/proj";
import { defaults as defaultControls } from "ol/control";

import { Circle as CircleStyle, Fill, Stroke, Style } from "ol/style";

import type { RouteFinderFilters } from "@/lib/types/route_finder";

import { greatCirclePoints } from "@/lib/route_map";

import RouteFilterBar from "./route_filter_bar";

import { boundingExtent } from "ol/extent";

// ============================================================
// Types
// ============================================================

interface Airport {
  icao: string;
  name: string;
  city: string | null;
  country: string | null;
  latitude: number;
  longitude: number;
}

interface SceneryResponse {
  source: string;
  airports: Airport[];
  missing: string[];
  connections: NetworkConnection[];
  connections_are_verified_routes: boolean;
}

interface NetworkConnection {
  id: string;
  from_icao: string;
  to_icao: string;
  distance_nm: number;
  classification: "verified" | "plausible";
  verified: boolean;
  directions: {
    from: string;
    to: string;
  }[];
  airlines: string[];
  aircraft: AircraftSuggestion[];
  reasons: string[];
}

interface AircraftSuggestion {
  id: number;
  name: string;
  icao: string | null;
  suitability: string;
  duration_min: number;
  score: number;
}

interface Connection extends NetworkConnection {
  from: Airport;
  to: Airport;
}

interface Props {
  filters: RouteFinderFilters;
  onChange: (patch: Partial<RouteFinderFilters>) => void;
  onReset: () => void;
}

interface TooltipState {
  x: number;
  y: number;
  connection: Connection;
}

interface SceneryMapProps {
  airports: Airport[];
  connections: Connection[];
  selected: string | null;
  onSelect: (id: string) => void;
}

type RouteFeature = Feature<LineString>;

// ============================================================
// Constants
// ============================================================

const COLORS = {
  normal: "#c75b9e",
  hovered: "#f0abfc",
  selected: "#facc15",
  airport: "#0284c7",
  background: "#090b12",
};

const DEFAULT_CENTER: [number, number] = [15, 15];

// ============================================================
// API
// ============================================================

async function loadScenery(
  signal?: AbortSignal,
  refresh = false,
  includePlausible = false,
  ownedOnly = true,
  maxDistanceNm = 10000,
): Promise<SceneryResponse> {
  const params = new URLSearchParams({
    refresh: String(refresh),
    include_plausible: String(includePlausible),
    owned_only: String(ownedOnly),
    max_distance_nm: String(maxDistanceNm),
  });

  const response = await fetch(`/api/route_finder/scenery?${params}`, {
    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Unable to load scenery (${response.status})`);
  }

  const data = (await response.json()) as SceneryResponse;

  if (!Array.isArray(data.airports) || !Array.isArray(data.connections)) {
    throw new Error("Unexpected scenery network response.");
  }

  return data;
}

// ============================================================
// Geographic helpers
// ============================================================

function unwrapPath(points: [number, number][]): [number, number][] {
  const result: [number, number][] = [];

  for (const [longitude, latitude] of points) {
    const previous = result.at(-1);

    const adjusted = previous
      ? longitude + 360 * Math.round((previous[0] - longitude) / 360)
      : longitude;

    result.push([adjusted, latitude]);
  }

  return result;
}

function connectionPath(connection: Connection): number[][] {
  const points = greatCirclePoints(
    [connection.from.longitude, connection.from.latitude],
    [connection.to.longitude, connection.to.latitude],
    96,
  );

  return unwrapPath(points).map((point) => fromLonLat(point));
}

function createRouteStyle(
  selected: boolean,
  hovered: boolean,
  classification: "verified" | "plausible",
): Style {
  const verified = classification === "verified";

  return new Style({
    stroke: new Stroke({
      color: selected
        ? COLORS.selected
        : hovered
          ? COLORS.hovered
          : verified
            ? "#c75b9e"
            : "#a78bfa",

      width: selected ? 3 : hovered ? 2.5 : verified ? 1.8 : 2,

      lineDash: verified ? undefined : [6, 6],
    }),

    zIndex: selected ? 30 : hovered ? 20 : 1,
  });
}

function createAirportStyle(selected: boolean): Style {
  return new Style({
    image: new CircleStyle({
      radius: selected ? 5 : 3.5,

      fill: new Fill({
        color: selected ? COLORS.selected : COLORS.airport,
      }),

      stroke: new Stroke({
        color: COLORS.background,
        width: selected ? 2 : 1,
      }),
    }),

    zIndex: selected ? 40 : 10,
  });
}

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// ============================================================
// OpenLayers scenery map
// ============================================================

function SceneryMap({
  airports,
  connections,
  selected,
  onSelect,
}: SceneryMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const mapRef = useRef<Map | null>(null);
  const routeSourceRef = useRef<VectorSource | null>(null);
  const airportSourceRef = useRef<VectorSource | null>(null);
  const routeFeaturesRef = useRef(new globalThis.Map<string, RouteFeature>());

  const airportFeaturesRef = useRef(
    new globalThis.Map<string, Feature<Point>>(),
  );

  const [hovered, setHovered] = useState<string | null>(null);

  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const connectionLookup = useMemo(
    () =>
      new globalThis.Map(
        connections.map((connection) => [connection.id, connection]),
      ),
    [connections],
  );

  const connectionLookupRef = useRef(connectionLookup);

  connectionLookupRef.current = connectionLookup;

  const selectedConnection = selected
    ? (connectionLookup.get(selected) ?? null)
    : null;

  // ----------------------------------------------------------
  // Initialize map
  // ----------------------------------------------------------

  useEffect(() => {
    const container = containerRef.current;

    if (!container) {
      return;
    }

    const routeSource = new VectorSource({
      wrapX: true,
    });

    const airportSource = new VectorSource({
      wrapX: true,
    });

    routeSourceRef.current = routeSource;
    airportSourceRef.current = airportSource;

    const baseLayer = new TileLayer({
      source: new XYZ({
        url: `https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png?key=${encodeURIComponent(process.env.NEXT_PUBLIC_CARTO_API_KEY ?? "")}`,

        wrapX: true,
        crossOrigin: "anonymous",

        attributions:
          '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · © <a href="https://carto.com/attributions">CARTO</a>',
      }),
    });

    const routeLayer = new VectorLayer({
      source: routeSource,
      renderBuffer: 200,
    });

    const airportLayer = new VectorLayer({
      source: airportSource,
      renderBuffer: 100,
    });

    const map = new Map({
      target: container,

      layers: [baseLayer, routeLayer, airportLayer],

      view: new View({
        center: fromLonLat(DEFAULT_CENTER),
        zoom: 2,
        minZoom: 1,
        maxZoom: 12,
        multiWorld: true,
      }),

      controls: defaultControls({
        zoom: false,
        rotate: false,
      }),
    });

    mapRef.current = map;

    // --------------------------------------------------------
    // Hit detection
    // --------------------------------------------------------

    const findRoute = (pixel: number[]): RouteFeature | null => {
      let found: RouteFeature | null = null;

      map.forEachFeatureAtPixel(
        pixel,

        (feature) => {
          if (feature.get("kind") !== "route") {
            return undefined;
          }

          found = feature as RouteFeature;

          return feature;
        },

        {
          hitTolerance: 7,

          layerFilter: (layer) => layer === routeLayer,
        },
      );

      return found;
    };

    // --------------------------------------------------------
    // Hover
    // --------------------------------------------------------

    map.on("pointermove", (event) => {
      if (event.dragging) {
        setHovered(null);
        setTooltip(null);
        return;
      }

      const feature = findRoute(event.pixel);

      if (!feature) {
        setHovered(null);
        setTooltip(null);

        map.getTargetElement()?.style.setProperty("cursor", "");

        return;
      }

      const id = feature.get("connectionId") as string;

      const connection = connectionLookupRef.current.get(id);

      if (!connection) {
        setHovered(null);
        setTooltip(null);
        return;
      }

      setHovered(id);

      setTooltip({
        x: event.pixel[0],
        y: event.pixel[1],
        connection,
      });

      map.getTargetElement()?.style.setProperty("cursor", "pointer");
    });

    // --------------------------------------------------------
    // Click
    // --------------------------------------------------------

    map.on("click", (event) => {
      const feature = findRoute(event.pixel);

      if (!feature) {
        return;
      }

      const id = feature.get("connectionId") as string;

      if (connectionLookupRef.current.has(id)) {
        onSelectRef.current(id);
      }
    });

    // --------------------------------------------------------
    // Pointer leave
    // --------------------------------------------------------

    const handlePointerLeave = () => {
      setHovered(null);
      setTooltip(null);

      map.getTargetElement()?.style.setProperty("cursor", "");
    };

    container.addEventListener("pointerleave", handlePointerLeave);

    // --------------------------------------------------------
    // Resize
    // --------------------------------------------------------

    const observer = new ResizeObserver(() => map.updateSize());

    observer.observe(container);

    // --------------------------------------------------------
    // Cleanup
    // --------------------------------------------------------

    return () => {
      observer.disconnect();

      container.removeEventListener("pointerleave", handlePointerLeave);

      map.setTarget(undefined);
      map.dispose();

      mapRef.current = null;
      routeSourceRef.current = null;
      airportSourceRef.current = null;

      routeFeaturesRef.current.clear();
      airportFeaturesRef.current.clear();
    };
  }, []);

  // ----------------------------------------------------------
  // Build route features
  // ----------------------------------------------------------

  useEffect(() => {
    const routeSource = routeSourceRef.current;

    const airportSource = airportSourceRef.current;

    if (!routeSource || !airportSource) {
      return;
    }

    routeSource.clear();
    airportSource.clear();

    routeFeaturesRef.current.clear();
    airportFeaturesRef.current.clear();

    for (const connection of connections) {
      const feature = new Feature({
        geometry: new LineString(connectionPath(connection)),
      });

      feature.set("kind", "route");

      feature.set("connectionId", connection.id);

      feature.set("classification", connection.classification);

      feature.setStyle(
        createRouteStyle(false, false, connection.classification),
      );

      routeSource.addFeature(feature);

      routeFeaturesRef.current.set(connection.id, feature);
    }

    for (const airport of airports) {
      const feature = new Feature({
        geometry: new Point(fromLonLat([airport.longitude, airport.latitude])),
      });

      feature.set("kind", "airport");

      feature.set("icao", airport.icao);

      feature.setStyle(createAirportStyle(false));

      airportSource.addFeature(feature);

      airportFeaturesRef.current.set(airport.icao, feature);
    }
  }, [connections, airports]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || airports.length === 0 || selected) {
      return;
    }

    const coordinates = airports.map((airport) =>
      fromLonLat([airport.longitude, airport.latitude]),
    );

    const extent = boundingExtent(coordinates);

    map.getView().fit(extent, {
      size: map.getSize(),
      padding: [100, 100, 100, 100],
      duration: 600,
      maxZoom: 5,
    });
  }, [airports, selected]);

  // ----------------------------------------------------------
  // Update feature styles
  // ----------------------------------------------------------

  useEffect(() => {
    for (const [id, feature] of routeFeaturesRef.current) {
      feature.setStyle(
        createRouteStyle(
          id === selected,
          id === hovered,
          feature.get("classification") === "verified"
            ? "verified"
            : "plausible",
        ),
      );
    }

    const selectedAirports = new Set<string>();

    if (selectedConnection) {
      selectedAirports.add(selectedConnection.from.icao);

      selectedAirports.add(selectedConnection.to.icao);
    }

    for (const [icao, feature] of airportFeaturesRef.current) {
      feature.setStyle(createAirportStyle(selectedAirports.has(icao)));
    }
  }, [selected, hovered, selectedConnection]);

  // ----------------------------------------------------------
  // Focus selected connection
  // ----------------------------------------------------------

  useEffect(() => {
    if (!selected) {
      return;
    }

    const map = mapRef.current;

    const feature = routeFeaturesRef.current.get(selected);

    const geometry = feature?.getGeometry();

    if (!map || !geometry) {
      return;
    }

    const size = map.getSize();

    if (!size) {
      return;
    }

    const rightPadding = Math.min(420, Math.max(60, size[0] * 0.32));

    map.getView().fit(geometry.getExtent(), {
      size,

      padding: [150, rightPadding, 100, 80],

      duration: reducedMotion() ? 0 : 850,

      maxZoom: 5,
    });
  }, [selected, connections]);

  // ----------------------------------------------------------
  // Tooltip position
  // ----------------------------------------------------------

  const tooltipStyle = useMemo(() => {
    if (!tooltip) {
      return {};
    }

    const width = containerRef.current?.clientWidth ?? 800;

    const height = containerRef.current?.clientHeight ?? 600;

    return {
      left: Math.min(Math.max(8, tooltip.x + 16), Math.max(8, width - 208)),

      top: Math.min(Math.max(8, tooltip.y - 72), Math.max(8, height - 80)),
    };
  }, [tooltip]);

  // ==========================================================
  // Render
  // ==========================================================

  return (
    <div className="relative h-full min-h-150 w-full overflow-hidden bg-[#090b12]">
      <div ref={containerRef} className="absolute inset-0" />

      {/* Hover tooltip */}

      {tooltip && (
        <div
          className="pointer-events-none absolute z-30 min-w-44 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-900 shadow-xl"
          style={tooltipStyle}
        >
          <div className="font-mono font-semibold">
            {tooltip.connection.from.icao}
            {" → "}
            {tooltip.connection.to.icao}
          </div>

          <p className="mt-1 text-[11px] text-zinc-500">
            Possible scenery connection
          </p>
        </div>
      )}

      {/* Legend */}

      <div className="pointer-events-none absolute bottom-5 left-5 z-10 flex flex-wrap items-center gap-4 rounded-lg border border-white/10 bg-[#111217]/90 px-3 py-2 text-[11px] text-zinc-400 shadow-xl backdrop-blur-md">
        <span className="flex items-center gap-2">
          <span className="h-0.5 w-5 bg-[#c75b9e]" />
          Possible connections
        </span>

        <span className="flex items-center gap-2">
          <span className="h-0.5 w-5 bg-[#facc15]" />
          Selected
        </span>

        <span className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-[#0284c7]" />
          Installed airports
        </span>
      </div>
    </div>
  );
}

// ============================================================
// Main scenery network
// ============================================================

export default function SceneryNetwork({ filters, onChange, onReset }: Props) {
  // ----------------------------------------------------------
  // Inventory query
  // ----------------------------------------------------------

const [includePlausible, setIncludePlausible] = useState(true);
const [ownedOnly, setOwnedOnly] = useState(false);
const [maxDistanceNm, setMaxDistanceNm] = useState(11000);

const query = useQuery({
  queryKey: [
    "route-finder",
    "installed-scenery",
    includePlausible,
    ownedOnly,
    maxDistanceNm,
  ],
  queryFn: ({ signal }) =>
    loadScenery(
      signal,
      false,
      includePlausible,
      ownedOnly,
      maxDistanceNm,
    ),
  staleTime: 60_000,
  retry: 1,
  refetchOnWindowFocus: false,
});

  // ----------------------------------------------------------
  // Valid installed airports
  // ----------------------------------------------------------

  const airports = useMemo(
    () =>
      (query.data?.airports ?? []).filter(
        (airport) =>
          /^[A-Z]{4}$/.test(airport.icao) &&
          Number.isFinite(airport.latitude) &&
          Number.isFinite(airport.longitude) &&
          Math.abs(airport.latitude) <= 90 &&
          Math.abs(airport.longitude) <= 180,
      ),
    [query.data],
  );

  // ----------------------------------------------------------
  // Filters
  // ----------------------------------------------------------


  // ----------------------------------------------------------
  // Possible connections
  // ----------------------------------------------------------

  const connections = useMemo((): Connection[] => {
  const lookup = new globalThis.Map<string, Airport>();

  for (const airport of airports) {
    lookup.set(airport.icao.trim().toUpperCase(), airport);
  }

  const result: Connection[] = [];

  for (const connection of query.data?.connections ?? []) {
    const from = lookup.get(
      connection.from_icao.trim().toUpperCase(),
    );

    const to = lookup.get(
      connection.to_icao.trim().toUpperCase(),
    );

    if (!from || !to) {
      console.warn(
        "[SceneryNetwork] Missing airport:",
        connection.from_icao,
        connection.to_icao,
      );
      continue;
    }

    result.push({
      ...connection,
      from,
      to,
    });
  }

  return result;
}, [airports, query.data?.connections]);

  // ----------------------------------------------------------
  // Selection and view
  // ----------------------------------------------------------

  const [selected, setSelected] = useState<string | null>(null);

  const [view, setView] = useState<"map" | "list">("map");

  const selectedPair = useMemo(
    () => connections.find((connection) => connection.id === selected) ?? null,
    [connections, selected],
  );

  // ----------------------------------------------------------
  // Clear invalid selection
  // ----------------------------------------------------------

  useEffect(() => {
    if (
      selected &&
      !connections.some((connection) => connection.id === selected)
    ) {
      setSelected(null);
    }
  }, [selected, connections]);

  // ==========================================================
  // Render
  // ==========================================================

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col overflow-hidden bg-[#090b12] text-zinc-100">
      {/* ======================================================
          Header
      ====================================================== */}

      <header className="relative z-30 flex flex-wrap items-center justify-between gap-4 border-b border-white/10 bg-[#0e0f13] px-6 py-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-white">
            Installed scenery network
          </h1>

          <p className="mt-1 text-xs text-zinc-500">
            Explore connections between airports detected in your MSFS scenery.
          </p>

          <p className="mt-2 text-[11px] text-zinc-600">
            Connections are possible pairs, not verified airline routes.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            void query.refetch();
          }}
          disabled={query.isFetching}
          className="flex h-9 items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 text-xs text-zinc-300 transition-colors hover:bg-white/10 disabled:opacity-50"
        >
          <RefreshCw
            className={[
              "size-3.5",
              query.isFetching ? "animate-spin" : "",
            ].join(" ")}
          />
          Refresh scenery
        </button>
      </header>

      {/* ======================================================
          Map workspace
      ====================================================== */}

      <main className="relative min-h-[calc(100vh-9rem)] flex-1 overflow-hidden">
        {/* Map or list */}

        <div className="absolute inset-0">
          {view === "map" ? (
            <SceneryMap
              airports={airports}
              connections={connections}
              selected={selectedPair?.id ?? null}
              onSelect={setSelected}
            />
          ) : (
            <div className="h-full overflow-auto bg-[#0b0c10] px-5 pb-8 pt-44">
              <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
                {/* Installed airports */}

                <section>
                  <h2 className="mb-4 text-sm font-semibold text-zinc-200">
                    Installed airports ({airports.length})
                  </h2>

                  <div className="overflow-hidden rounded-xl border border-white/10 bg-[#111217]">
                    {airports.map((airport) => (
                      <div
                        key={airport.icao}
                        className="flex items-start gap-3 border-b border-white/5 px-4 py-3 text-sm last:border-b-0"
                      >
                        <span className="shrink-0 font-mono text-amber-400">
                          {airport.icao}
                        </span>

                        <div className="min-w-0">
                          <p className="truncate text-zinc-300">
                            {airport.name}
                          </p>

                          <p className="mt-1 text-xs text-zinc-500">
                            {[airport.city, airport.country]
                              .filter(Boolean)
                              .join(", ")}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                {/* Connections */}

                <section>
                  <h2 className="mb-4 text-sm font-semibold text-zinc-200">
                    Possible connections ({connections.length})
                  </h2>

                  <div className="overflow-hidden rounded-xl border border-white/10 bg-[#111217]">
                    {connections.map((connection) => (
                      <button
                        key={connection.id}
                        type="button"
                        onClick={() => {
                          setSelected(connection.id);

                          setView("map");
                        }}
                        className="flex w-full items-center justify-between border-b border-white/5 px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-white/5"
                      >
                        <span className="font-mono text-xs text-zinc-300">
                          {connection.from.icao}
                          {" → "}
                          {connection.to.icao}
                        </span>

                        <span className="text-[11px] text-zinc-600">
                          View on map
                        </span>
                      </button>
                    ))}
                  </div>
                </section>
              </div>
            </div>
          )}
        </div>

        {/* ====================================================
            Floating toolbar
        ==================================================== */}

        <div className="pointer-events-none absolute inset-x-0 top-4 z-30 flex justify-center px-4">
          <div className="pointer-events-auto w-full max-w-6xl rounded-2xl border border-white/10 bg-[#111217]/95 shadow-2xl backdrop-blur-xl">
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-zinc-500">
                <span>
                  <strong className="text-zinc-300">
                    {airports.length.toLocaleString()}
                  </strong>{" "}
                  installed airports
                </span>

                <span>
                  <strong className="text-amber-400">
                    {connections.length.toLocaleString()}
                  </strong>{" "}
                  possible connections
                </span>

                {query.isFetching && (
                  <span className="flex items-center gap-1.5">
                    <LoaderCircle className="size-3 animate-spin" />
                    Scanning scenery
                  </span>
                )}
              </div>

              {/* View switcher */}

              <div className="flex items-center rounded-lg border border-white/10 bg-[#0b0c10] p-1">
                <button
                  type="button"
                  onClick={() => setView("map")}
                  aria-pressed={view === "map"}
                  className={[
                    "flex h-8 items-center gap-2 rounded-md px-3 text-xs transition-colors",
                    view === "map"
                      ? "bg-amber-400 text-zinc-950"
                      : "text-zinc-400 hover:bg-white/5 hover:text-white",
                  ].join(" ")}
                >
                  <MapIcon className="size-3.5" />
                  Map
                </button>

                <button
                  type="button"
                  onClick={() => setView("list")}
                  aria-pressed={view === "list"}
                  className={[
                    "flex h-8 items-center gap-2 rounded-md px-3 text-xs transition-colors",
                    view === "list"
                      ? "bg-amber-400 text-zinc-950"
                      : "text-zinc-400 hover:bg-white/5 hover:text-white",
                  ].join(" ")}
                >
                  <Table2 className="size-3.5" />
                  List
                </button>
              </div>
            </div>

            {/* Existing filters */}

            <div className="flex flex-wrap items-center gap-5 border-t border-white/10 px-4 py-3 text-xs text-zinc-300">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={includePlausible}
                  onChange={(event) =>
                    setIncludePlausible(event.target.checked)
                  }
                  className="accent-amber-400"
                />
                Show plausible connections
              </label>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={ownedOnly}
                  onChange={(event) => setOwnedOnly(event.target.checked)}
                  className="accent-amber-400"
                />
                Owned aircraft only
              </label>

              <label className="flex items-center gap-3">
                <span className="text-zinc-500">Maximum distance</span>

                <select
                  value={maxDistanceNm}
                  onChange={(event) =>
                    setMaxDistanceNm(Number(event.target.value))
                  }
                  className="rounded-md border border-white/10 bg-[#0b0c10] px-2 py-1.5 text-zinc-200"
                >
                  <option value={1000}>1,000 NM</option>
                  <option value={2000}>2,000 NM</option>
                  <option value={4000}>4,000 NM</option>
                  <option value={6000}>6,000 NM</option>
                  <option value={8000}>8,000 NM</option>
                  <option value={10000}>10,000 NM</option>
                  <option value={11000}>11,000 NM</option>
                </select>
              </label>
            </div>

            <div className="[&_form]:rounded-b-2xl [&_form]:border-b-0 [&_form]:bg-transparent [&_form]:px-4 [&_form]:py-3">
              <RouteFilterBar
                filters={filters}
                loading={query.isFetching}
                onChange={onChange}
                onReset={onReset}
                onGenerate={() => {
                  void query.refetch();
                }}
              />
            </div>
          </div>
        </div>

        {/* ====================================================
            Error / loading
        ==================================================== */}

        {query.error && (
          <div className="pointer-events-none absolute inset-x-4 top-40 z-20 mx-auto max-w-2xl">
            <div className="flex items-center gap-3 rounded-xl border border-red-500/20 bg-[#211318]/95 px-4 py-3 text-sm text-red-300 shadow-xl">
              <AlertCircle className="size-4 shrink-0" />

              <span>
                {query.error instanceof Error
                  ? query.error.message
                  : "Unable to load scenery."}
              </span>
            </div>
          </div>
        )}

        {query.isPending && (
          <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center">
            <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-[#111217]/95 px-5 py-4 text-sm text-zinc-300 shadow-xl">
              <LoaderCircle className="size-4 animate-spin text-amber-400" />
              Loading installed scenery...
            </div>
          </div>
        )}

        {/* ====================================================
            Selected connection panel
        ==================================================== */}

        {view === "map" && selectedPair && (
          <aside className="absolute bottom-5 right-5 top-40 z-20 flex w-[min(370px,calc(100%-40px))] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#111217]/95 shadow-2xl backdrop-blur-xl">
            <div className="flex items-center justify-between border-b border-white/10 bg-[#14161c] px-4 py-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
                  Selected connection
                </p>

                <p className="mt-1 font-mono text-xs font-medium text-amber-400">
                  {selectedPair.from.icao}
                  {" → "}
                  {selectedPair.to.icao}
                </p>
              </div>

              <div className="mt-5 space-y-3 rounded-xl border border-white/10 bg-white/5 p-4 text-xs">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Classification</span>

                  <span className="font-medium text-zinc-200">
                    {selectedPair.classification === "verified"
                      ? "Verified catalog route"
                      : "Plausible connection"}
                  </span>
                </div>

                <div className="flex justify-between">
                  <span className="text-zinc-500">Distance</span>

                  <span className="font-mono text-zinc-200">
                    {selectedPair.distance_nm.toLocaleString()} NM
                  </span>
                </div>

                <div>
                  <p className="mb-2 text-zinc-500">Airlines</p>

                  <p className="text-zinc-200">
                    {selectedPair.airlines.length
                      ? selectedPair.airlines.join(", ")
                      : "No verified airline assignment"}
                  </p>
                </div>

                <div>
                  <p className="mb-2 text-zinc-500">Compatible aircraft</p>

                  {selectedPair.aircraft.length ? (
                    <div className="space-y-2">
                      {selectedPair.aircraft.map((aircraft) => (
                        <div
                          key={aircraft.id}
                          className="flex justify-between gap-3"
                        >
                          <span>{aircraft.name}</span>
                          <span className="text-zinc-500">
                            {Math.round((aircraft.duration_min / 60) * 10) / 10}
                            h
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-zinc-500">
                      No compatible aircraft established.
                    </p>
                  )}
                </div>
              </div>

              <button
                type="button"
                aria-label="Close connection details"
                onClick={() => setSelected(null)}
                className="flex size-8 items-center justify-center rounded-lg border border-white/10 text-zinc-400 hover:bg-white/10 hover:text-white"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-mono text-2xl font-bold text-white">
                    {selectedPair.from.icao}
                  </p>

                  <p className="mt-1 truncate text-xs text-zinc-500">
                    {selectedPair.from.name}
                  </p>
                </div>

                <span className="shrink-0 text-lg text-amber-400">→</span>

                <div className="min-w-0 text-right">
                  <p className="font-mono text-2xl font-bold text-white">
                    {selectedPair.to.icao}
                  </p>

                  <p className="mt-1 truncate text-xs text-zinc-500">
                    {selectedPair.to.name}
                  </p>
                </div>
              </div>

              <div className="mt-6 rounded-xl border border-white/10 bg-white/5 px-4 py-4">
                <p className="text-xs font-medium text-zinc-300">
                  Installed scenery
                </p>

                <p className="mt-2 text-xs leading-5 text-zinc-500">
                  Both airports were detected in your installed MSFS scenery
                  inventory. This connection does not imply scheduled airline
                  service or aircraft compatibility.
                </p>
              </div>

              <div className="mt-6 space-y-4 text-xs">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-zinc-500">Departure</span>

                  <span className="text-right text-zinc-300">
                    {selectedPair.from.city ?? selectedPair.from.name}
                  </span>
                </div>

                <div className="border-t border-white/10" />

                <div className="flex items-start justify-between gap-3">
                  <span className="text-zinc-500">Arrival</span>

                  <span className="text-right text-zinc-300">
                    {selectedPair.to.city ?? selectedPair.to.name}
                  </span>
                </div>

                <div className="border-t border-white/10" />

                <div className="flex items-start justify-between gap-3">
                  <span className="text-zinc-500">Connection type</span>

                  <span className="text-right text-zinc-300">
                    Possible airport pair
                  </span>
                </div>
              </div>
            </div>
          </aside>
        )}

        {/* Empty state */}

        {!query.isPending && !query.error && airports.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="rounded-xl border border-white/10 bg-[#111217]/95 px-6 py-5 text-center shadow-xl">
              <p className="text-sm font-medium text-zinc-300">
                No installed scenery detected
              </p>

              <p className="mt-2 max-w-sm text-xs leading-5 text-zinc-500">
                Check your configured MSFS package directories and refresh the
                scenery inventory.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
