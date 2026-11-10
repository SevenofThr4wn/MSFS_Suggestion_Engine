"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { buildRouteGeometry } from "@/lib/route_map";
import type { RouteFinderFilters } from "@/lib/types/route_finder";
import RouteFilterBar from "./route_filter_bar";

type Airport = {
  icao: string;
  name: string;
  city: string | null;
  country: string | null;
  latitude: number;
  longitude: number;
};
type SceneryResponse = {
  source: string;
  airports: Airport[];
  missing: string[];
  connections_are_verified_routes: false;
};
type Connection = { id: string; from: Airport; to: Airport };

async function loadScenery(signal?: AbortSignal): Promise<SceneryResponse> {
  const response = await fetch("/api/route_finder/scenery", {
    signal,
    cache: "no-store",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      error.detail ?? `Unable to load installed scenery (${response.status})`,
    );
  }
  const data = (await response.json()) as SceneryResponse;
  if (!Array.isArray(data.airports))
    throw new Error("Unexpected scenery response");
  return data;
}

interface Props {
  filters: RouteFinderFilters;
  onChange: (patch: Partial<RouteFinderFilters>) => void;
  onReset: () => void;
}

export default function SceneryNetwork({ filters, onChange, onReset }: Props) {
  const query = useQuery({
    queryKey: ["route-finder", "installed-scenery"],
    queryFn: ({ signal }) => loadScenery(signal),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
  const airports = query.data?.airports ?? [];
  const departure = filters.departureCode.trim().toUpperCase();
  const arrival = filters.arrivalCode.trim().toUpperCase();

  const connections = useMemo(() => {
    const pairs: Connection[] = [];
    for (let a = 0; a < airports.length; a++) {
      for (let b = a + 1; b < airports.length; b++) {
        const from = airports[a];
        const to = airports[b];
        if (departure && from.icao !== departure && to.icao !== departure)
          continue;
        if (arrival && from.icao !== arrival && to.icao !== arrival) continue;
        if (
          departure &&
          arrival &&
          !(
            (from.icao === departure && to.icao === arrival) ||
            (from.icao === arrival && to.icao === departure)
          )
        )
          continue;
        pairs.push({ id: `${from.icao}-${to.icao}`, from, to });
      }
    }
    return pairs;
  }, [airports, departure, arrival]);

  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<"map" | "list">("map");
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const current = useRef({ connections, selected, setSelected });
  current.current = { connections, selected, setSelected };

  useEffect(() => {
    if (view !== "map" || !mapContainer.current) return;
    let disposed = false;
    let map: MapLibreMap | null = null;
    void import("maplibre-gl")
      .then((lib) => {
        if (disposed || !mapContainer.current) return;
        map = new lib.Map({
          container: mapContainer.current,
          style:
            "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
          center: [20, 10],
          zoom: 1.3,
          minZoom: 1,
          attributionControl: {
            compact: true,
          },
        });
        const m = map;
        mapRef.current = m;
        m.on("style.load", () => m.setProjection({ type: "globe" }));
        m.addControl(
          new lib.NavigationControl({ showCompass: false }),
          "bottom-right",
        );
        m.on("load", () => {
          if (disposed) return;
          m.addSource("scenery-connections", {
            type: "geojson",
            data: { type: "FeatureCollection", features: [] },
          });
          m.addSource("scenery-airports", {
            type: "geojson",
            data: { type: "FeatureCollection", features: [] },
          });
          m.addLayer({
            id: "scenery-lines",
            type: "line",
            source: "scenery-connections",
            paint: {
              "line-color": [
                "case",
                ["boolean", ["get", "selected"], false],
                "#facc15",
                "#a855f7",
              ],
              "line-width": [
                "case",
                ["boolean", ["get", "selected"], false],
                3,
                1.3,
              ],
              "line-opacity": 0.65,
            },
          });
          m.addLayer({
            id: "scenery-hit",
            type: "line",
            source: "scenery-connections",
            paint: {
              "line-color": "#fff",
              "line-opacity": 0,
              "line-width": 12,
            },
          });
          m.addLayer({
            id: "scenery-points",
            type: "circle",
            source: "scenery-airports",
            paint: {
              "circle-color": "#facc15",
              "circle-radius": 4,
              "circle-stroke-color": "#0b0c10",
              "circle-stroke-width": 2,
            },
          });
          m.addLayer({
            id: "scenery-labels",
            type: "symbol",
            source: "scenery-airports",
            layout: {
              "text-field": ["get", "icao"],
              "text-size": 11,
              "text-offset": [0, 1.3],
            },
            paint: {
              "text-color": "#fff",
              "text-halo-color": "#0b0c10",
              "text-halo-width": 2,
            },
          });
          m.on("click", "scenery-hit", (e) => {
            const id = e.features?.[0]?.properties?.id;
            if (typeof id === "string") current.current.setSelected(id);
          });
          m.on("mouseenter", "scenery-hit", () => {
            m.getCanvas().style.cursor = "pointer";
          });
          m.on("mouseleave", "scenery-hit", () => {
            m.getCanvas().style.cursor = "";
          });
          setMapReady(true);
        });
      })
      .catch(console.error);
    return () => {
      disposed = true;
      mapRef.current = null;
      map?.remove();
      setMapReady(false);
    };
  }, [view]);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !mapReady) return;
    const source = m.getSource("scenery-connections") as
      | import("maplibre-gl").GeoJSONSource
      | undefined;
    source?.setData({
      type: "FeatureCollection",
      features: connections.map((c) => ({
        type: "Feature" as const,
        properties: { id: c.id, selected: c.id === selected },
        geometry: buildRouteGeometry(c.from, c.to),
      })),
    });
    const airportSource = m.getSource("scenery-airports") as
      | import("maplibre-gl").GeoJSONSource
      | undefined;
    // Show all installed airports, even when a route filter excludes connections.
    airportSource?.setData({
      type: "FeatureCollection",
      features: airports.map((a) => ({
        type: "Feature" as const,
        properties: { icao: a.icao, name: a.name },
        geometry: {
          type: "Point" as const,
          coordinates: [a.longitude, a.latitude],
        },
      })),
    });
  }, [connections, airports, selected, mapReady]);

  const selectedPair = connections.find((c) => c.id === selected) ?? null;

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col bg-[#0b0c10] text-zinc-100">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-6 py-4">
        <div>
          <h1 className="text-xl font-semibold">Installed scenery network</h1>
          <p className="mt-1 text-xs text-zinc-400">
            Connections between airports with installed scenery. These are
            possible pairs, not verified airline routes.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="rounded-lg border border-white/15 px-3 py-2 text-xs"
            onClick={() => setView(view === "map" ? "list" : "map")}
          >
            {view === "map" ? "Show list" : "Show globe"}
          </button>
          <button
            className="rounded-lg border border-white/15 px-3 py-2 text-xs"
            onClick={() => void query.refetch()}
          >
            Refresh scenery
          </button>
        </div>
      </header>
      <RouteFilterBar
        filters={filters}
        loading={query.isFetching}
        onChange={onChange}
        onReset={onReset}
        onGenerate={() => void query.refetch()}
      />
      <div className="border-b border-white/10 px-6 py-3 text-xs text-zinc-400">
        {airports.length} installed airports · {connections.length} possible
        connections · No route engine or aircraft predictions
      </div>
      {query.error && (
        <p className="px-6 py-4 text-sm text-red-400">
          {query.error instanceof Error
            ? query.error.message
            : "Unable to load scenery"}
        </p>
      )}
      {query.isPending && (
        <p className="px-6 py-4 text-sm text-zinc-400">
          Loading installed scenery…
        </p>
      )}
      {!query.isPending && !query.error && airports.length === 0 && (
        <p className="px-6 py-5 text-sm text-zinc-400">
          No installed scenery airports have been marked in Airport Preferences.
        </p>
      )}
      {view === "map" ? (
        <div className="relative min-h-155 flex-1">
          <div ref={mapContainer} className="absolute inset-0" />
          {selectedPair && (
            <div className="absolute bottom-5 left-5 rounded-xl border border-white/15 bg-[#111217]/95 px-4 py-3 text-xs shadow-lg">
              <div className="font-mono text-amber-400">
                {selectedPair.from.icao} → {selectedPair.to.icao}
              </div>
              <div className="mt-1 text-zinc-400">
                Scenery available at both airports
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="grid min-h-112.5 grid-cols-1 gap-4 overflow-auto p-5 lg:grid-cols-2">
          <section>
            <h2 className="mb-3 text-sm font-semibold">
              Installed airports ({airports.length})
            </h2>
            {airports.map((a) => (
              <div
                key={a.icao}
                className="border-b border-white/10 py-2 text-sm"
              >
                <span className="mr-3 font-mono text-amber-400">{a.icao}</span>
                {a.name}
              </div>
            ))}
          </section>
          <section>
            <h2 className="mb-3 text-sm font-semibold">
              Connections ({connections.length})
            </h2>
            {connections.map((c) => (
              <button
                key={c.id}
                className="block w-full border-b border-white/10 py-2 text-left font-mono text-xs text-zinc-300 hover:text-amber-400"
                onClick={() => {
                  setSelected(c.id);
                  setView("map");
                }}
              >
                {c.from.icao} → {c.to.icao}
              </button>
            ))}
          </section>
        </div>
      )}
    </div>
  );
}
