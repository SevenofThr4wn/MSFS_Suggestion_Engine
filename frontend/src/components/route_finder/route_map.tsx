"use client";

import { useEffect, useRef, useState } from "react";
import { Globe2, LoaderCircle, MapPinOff } from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { ScoredRecommendation } from "@/lib/types/recommendation";
import type { AirportCoordinateLookup } from "@/lib/types/route_finder";
import { getRouteCoordinates, routeBounds } from "@/lib/route_map";
import { routeKey } from "@/lib/route_finder";

import { initializeRouteAnimation, animateRoute } from "./route_animation";

import {
  initializeRouteMapLayers,
  updateRouteMapLayers,
  ROUTE_HIT_LAYER,
} from "./route_map_layer";

const DARK_MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

interface RouteMapProps {
  routes: ScoredRecommendation[];

  airports: AirportCoordinateLookup;

  selectedKey: string | null;

  onSelect: (route: ScoredRecommendation) => void;
}

interface CurrentMapData {
  routes: ScoredRecommendation[];
  airports: AirportCoordinateLookup;
  selectedKey: string | null;
  onSelect: RouteMapProps["onSelect"];
}

function focusRoute(
  map: MapLibreMap,
  routes: ScoredRecommendation[],
  airports: AirportCoordinateLookup,
  selectedKey: string | null,
  animate: boolean,
): void {
  if (!selectedKey) {
    return;
  }

  const selected = routes.find((item) => routeKey(item) === selectedKey);

  if (!selected) {
    return;
  }

  const coordinates = getRouteCoordinates(selected, airports);

  if (!coordinates) {
    return;
  }

  const bounds = routeBounds(coordinates.departure, coordinates.arrival);

  map.fitBounds(bounds, {
    padding: {
      top: 75,
      bottom: 75,
      left: 65,
      right: 65,
    },

    maxZoom: 6,
    duration: animate ? 850 : 0,
  });
}

export default function RouteMap({
  routes,
  airports,
  selectedKey,
  onSelect,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const dataRef = useRef<CurrentMapData>({
    routes,
    airports,
    selectedKey,
    onSelect,
  });

  const [ready, setReady] = useState(false);
  const [isGlobe, setIsGlobe] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    let cancelled = false;
    let instance: MapLibreMap | null = null;

    async function initialize() {
      try {
        const maplibregl = await import("maplibre-gl");

        if (cancelled || !containerRef.current) {
          return;
        }

        const map = new maplibregl.Map({
          container: containerRef.current,

          style: DARK_MAP_STYLE,

          center: [20, 15],
          zoom: 1.5,

          minZoom: 1,
          maxZoom: 12,

          attributionControl: false,
        });

        instance = map;
        mapRef.current = map;

        map.addControl(
          new maplibregl.NavigationControl({
            showCompass: false,
            showZoom: true,
          }),
          "bottom-right",
        );

        map.addControl(
          new maplibregl.AttributionControl({
            compact: true,
          }),
          "bottom-left",
        );

        // Configure the globe once. Switching projection later must
        // not be undone by a style-load callback.
        map.setProjection({ type: "globe" });

        map.on("load", () => {
          if (cancelled) {
            return;
          }

          initializeRouteMapLayers(map);
          initializeRouteAnimation(map);

          const current = dataRef.current;

          updateRouteMapLayers(
            map,
            current.routes,
            current.airports,
            current.selectedKey,
          );

          focusRoute(
            map,
            current.routes,
            current.airports,
            current.selectedKey,
            false,
          );

          setReady(true);
        });

        map.on("click", ROUTE_HIT_LAYER, (event) => {
          const key = event.features?.[0]?.properties?.routeKey;

          if (typeof key !== "string") {
            return;
          }

          const current = dataRef.current;

          const selected = current.routes.find(
            (item) => routeKey(item) === key,
          );

          if (selected) {
            current.onSelect(selected);
          }
        });

        map.on("mouseenter", ROUTE_HIT_LAYER, () => {
          map.getCanvas().style.cursor = "pointer";
        });

        map.on("mouseleave", ROUTE_HIT_LAYER, () => {
          map.getCanvas().style.cursor = "";
        });

        map.on("error", (event) => {
          if (cancelled) {
            return;
          }

          console.error("ROUTE MAP ERROR |", event.error);
        });
      } catch (cause) {
        if (cancelled) {
          return;
        }

        console.error("MAP INITIALIZATION ERROR |", cause);

        setError("Unable to initialize the route map.");
      }
    }

    void initialize();

    return () => {
      cancelled = true;

      instance?.remove();

      if (mapRef.current === instance) {
        mapRef.current = null;
      }
    };
  }, []);

  function toggleGlobe() {
    const map = mapRef.current;
    if (!map || !ready) return;

    const next = !isGlobe;
    map.setProjection({ type: next ? "globe" : "mercator" });
    setIsGlobe(next);
  }

  // Hooks must run at the top level of the component, never from
  // map event handlers. Cleanup cancels the previous flight animation.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    const selected = selectedKey
      ? routes.find((item) => routeKey(item) === selectedKey)
      : undefined;

    const coordinates = selected
      ? getRouteCoordinates(selected, airports)
      : null;

    if (!coordinates) return;

    return animateRoute(map, coordinates);
  }, [ready, routes, airports, selectedKey]);

  useEffect(() => {
    dataRef.current = {
      routes,
      airports,
      selectedKey,
      onSelect,
    };
  }, [routes, airports, selectedKey, onSelect]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !ready) {
      return;
    }

    updateRouteMapLayers(map, routes, airports, selectedKey);
  }, [ready, routes, airports, selectedKey]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !ready) {
      return;
    }

    focusRoute(map, routes, airports, selectedKey, true);
  }, [ready, routes, airports, selectedKey]);

  const mappedCount = routes.filter(
    (item) => getRouteCoordinates(item, airports) !== null,
  ).length;

  return (
    <div className="relative h-full min-h-150 w-full overflow-hidden bg-[#0d0f14]">
      <div ref={containerRef} className="absolute inset-0" />

      <button
        type="button"
        onClick={toggleGlobe}
        disabled={!ready}
        className="
        absolute right-5 top-5 z-20
        rounded-lg border border-white/10
        bg-[#121318]/90 px-4 py-2
        text-xs font-medium text-zinc-200
        shadow-xl backdrop-blur-md
        transition-colors hover:bg-zinc-800
        disabled:opacity-50
      "
      >
        {isGlobe ? "2D Map" : "3D Globe"}
      </button>

      <div className="pointer-events-none absolute left-5 top-5 z-10 rounded-xl border border-white/10 bg-[#121318]/90 px-4 py-3 shadow-xl backdrop-blur-md">
        <div className="flex items-center gap-2">
          <Globe2 className="size-4 text-amber-400" />

          <span className="text-xs font-semibold text-zinc-200">Route Map</span>
        </div>

        <p className="mt-1 text-[11px] text-zinc-500">
          {mappedCount.toLocaleString()} of {routes.length.toLocaleString()}{" "}
          routes mapped
        </p>

        {routes.length > 0 && (
          <p className="mt-1 text-[10px] text-zinc-600">
            Click a route to view its details
          </p>
        )}
      </div>

      <div className="pointer-events-none absolute bottom-6 left-5 z-10 rounded-lg border border-white/10 bg-[#121318]/90 px-3 py-2 shadow-xl backdrop-blur-md">
        <div className="flex items-center gap-4 text-[11px] text-zinc-400">
          <div className="flex items-center gap-2">
            <span className="h-0.5 w-5 bg-fuchsia-500" />
            Suggested
          </div>

          <div className="flex items-center gap-2">
            <span className="h-0.5 w-5 bg-amber-400" />
            Selected
          </div>
        </div>
      </div>

      {!ready && !error && (
        <div className="pointer-events-none absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-[#0d0f14]">
          <LoaderCircle className="size-6 animate-spin text-amber-400" />

          <p className="text-sm text-zinc-400">Loading world map...</p>
        </div>
      )}

      {ready && routes.length === 0 && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
          <div className="rounded-xl border border-white/10 bg-[#121318]/95 px-6 py-5 text-center shadow-xl">
            <Globe2 className="mx-auto size-6 text-zinc-500" />

            <p className="mt-3 text-sm font-medium text-zinc-300">
              No routes to display
            </p>

            <p className="mt-2 max-w-xs text-xs leading-5 text-zinc-500">
              Generate recommendations to see flight paths.
            </p>
          </div>
        </div>
      )}

      {ready && routes.length > 0 && mappedCount === 0 && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
          <div className="rounded-xl border border-white/10 bg-[#121318]/95 px-6 py-5 text-center shadow-xl">
            <MapPinOff className="mx-auto size-6 text-zinc-500" />

            <p className="mt-3 text-sm font-medium text-zinc-300">
              Airport coordinates unavailable
            </p>

            <p className="mt-2 max-w-xs text-xs leading-5 text-zinc-500">
              Route locations could not be loaded from FlightEngine.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#0d0f14] px-6 text-center">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}
    </div>
  );
}
