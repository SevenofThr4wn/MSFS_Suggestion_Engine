"use client";

import { useEffect, useMemo, useRef, useState } from "react";

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

import type { ScoredRecommendation } from "@/lib/types/recommendation";
import type { AirportCoordinateLookup } from "@/lib/types/route_finder";

import { formatDuration, routeKey } from "@/lib/route_finder";

import { getRouteCoordinates, greatCirclePoints } from "@/lib/route_map";

// ============================================================
// Types
// ============================================================

interface RouteMapProps {
  routes: ScoredRecommendation[];
  airports: AirportCoordinateLookup;
  selectedKey: string | null;
  onSelect: (route: ScoredRecommendation) => void;
}

interface RouteGroup {
  id: string;
  departure: string;
  arrival: string;
  routes: ScoredRecommendation[];
  representative: ScoredRecommendation;
  coordinates: [number, number][];
}

interface TooltipState {
  x: number;
  y: number;
  departure: string;
  arrival: string;
  duration: string;
  count: number;
}

type RouteFeature = Feature<LineString>;

interface RouteFeatureProperties {
  groupId: string;
  kind: "route";
}

// ============================================================
// Constants
// ============================================================

const COLORS = {
  normal: "#c75b9e",
  hovered: "#f0abfc",
  selected: "#facc15",
  airport: "#0284c7",
  selectedAirport: "#facc15",
  background: "#090b12",
};

const DEFAULT_CENTER: [number, number] = [15, 15];

const DEFAULT_ZOOM = 2;

const SELECTED_PADDING = [150, 420, 100, 80];

const MIN_ZOOM = 1;
const MAX_ZOOM = 12;

// ============================================================
// Helpers
// ============================================================

function pairKey(departure: string, arrival: string): string {
  return [departure, arrival].sort().join("-");
}

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

function createRouteStyle(selected: boolean, hovered: boolean): Style {
  return new Style({
    stroke: new Stroke({
      color: selected
        ? COLORS.selected
        : hovered
          ? COLORS.hovered
          : COLORS.normal,
      width: selected ? 3 : hovered ? 2.5 : 1.4,
    }),
    zIndex: selected ? 30 : hovered ? 20 : 1,
  });
}

function createAirportStyle(selected: boolean): Style {
  return new Style({
    image: new CircleStyle({
      radius: selected ? 5 : 3.5,
      fill: new Fill({
        color: selected ? COLORS.selectedAirport : COLORS.airport,
      }),
      stroke: new Stroke({
        color: COLORS.background,
        width: selected ? 2 : 1,
      }),
    }),
    zIndex: selected ? 40 : 10,
  });
}

function getGroupDuration(group: RouteGroup): string {
  const minutes = group.representative.route.estimated_duration_min;

  if (!Number.isFinite(minutes)) {
    return "Duration unavailable";
  }

  return formatDuration(minutes);
}

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// ============================================================
// Component
// ============================================================

export default function RouteMap({
  routes,
  airports,
  selectedKey,
  onSelect,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const mapRef = useRef<Map | null>(null);

  const routeSourceRef = useRef<VectorSource | null>(null);
  const airportSourceRef = useRef<VectorSource | null>(null);

  const routeFeaturesRef = useRef(new globalThis.Map<string, RouteFeature>());

  const airportFeaturesRef = useRef(
    new globalThis.Map<string, Feature<Point>>(),
  );

  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const [hoveredGroupId, setHoveredGroupId] = useState<string | null>(null);

  // ==========================================================
  // Group routes by airport pair
  // ==========================================================

  const groups = useMemo<RouteGroup[]>(() => {
    const grouped = new globalThis.Map<string, RouteGroup>();

    for (const route of routes) {
      const coordinates = getRouteCoordinates(route, airports);

      if (!coordinates) {
        continue;
      }

      const departure = route.route.departure_icao;
      const arrival = route.route.arrival_icao;

      const id = pairKey(departure, arrival);

      const existing = grouped.get(id);

      if (existing) {
        existing.routes.push(route);
        continue;
      }

      const path = unwrapPath(
        greatCirclePoints(
          [coordinates.departure.longitude, coordinates.departure.latitude],
          [coordinates.arrival.longitude, coordinates.arrival.latitude],
          96,
        ),
      );

      grouped.set(id, {
        id,
        departure,
        arrival,
        routes: [route],
        representative: route,
        coordinates: path,
      });
    }

    return [...grouped.values()];
  }, [routes, airports]);

  const groupLookup = useMemo(
    () => new globalThis.Map(groups.map((group) => [group.id, group])),
    [groups],
  );

  const routeToGroup = useMemo(() => {
    const lookup = new globalThis.Map<string, string>();

    for (const group of groups) {
      for (const route of group.routes) {
        lookup.set(routeKey(route), group.id);
      }
    }

    return lookup;
  }, [groups]);

  const selectedGroupId = selectedKey
    ? (routeToGroup.get(selectedKey) ?? null)
    : null;

  const groupLookupRef = useRef(groupLookup);
  groupLookupRef.current = groupLookup;

  const selectedGroupIdRef = useRef(selectedGroupId);
  selectedGroupIdRef.current = selectedGroupId;

  // ==========================================================
  // Initialize OpenLayers
  // ==========================================================

  useEffect(() => {
    if (!containerRef.current) {
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
      target: containerRef.current,
      layers: [baseLayer, routeLayer, airportLayer],
      view: new View({
        center: fromLonLat(DEFAULT_CENTER),
        zoom: DEFAULT_ZOOM,
        minZoom: MIN_ZOOM,
        maxZoom: MAX_ZOOM,
        multiWorld: true,
      }),
      controls: defaultControls({
        zoom: false,
        rotate: false,
      }),
    });

    mapRef.current = map;

    // --------------------------------------------------------
    // Route hit detection
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
        setHoveredGroupId(null);
        setTooltip(null);
        return;
      }

      const feature = findRoute(event.pixel);

      if (!feature) {
        setHoveredGroupId(null);
        setTooltip(null);

        map.getTargetElement()?.style.setProperty("cursor", "");

        return;
      }

      const groupId = feature.get("groupId") as string;

      const group = groupLookupRef.current.get(groupId);

      if (!group) {
        setHoveredGroupId(null);
        setTooltip(null);
        return;
      }

      setHoveredGroupId(groupId);

      setTooltip({
        x: event.pixel[0],
        y: event.pixel[1],
        departure: group.departure,
        arrival: group.arrival,
        duration: getGroupDuration(group),
        count: group.routes.length,
      });

      map.getTargetElement()?.style.setProperty("cursor", "pointer");
    });

    // --------------------------------------------------------
    // Click selection
    // --------------------------------------------------------

    map.on("click", (event) => {
      const feature = findRoute(event.pixel);

      if (!feature) {
        return;
      }

      const groupId = feature.get("groupId") as string;

      const group = groupLookupRef.current.get(groupId);

      if (!group) {
        return;
      }

      // Prefer the already-selected recommendation
      // when clicking a grouped route.
      const selected = group.routes.find(
        (route) => routeKey(route) === selectedKeyRef.current,
      );

      onSelectRef.current(selected ?? group.representative);
    });

    const handlePointerLeave = () => {
      setHoveredGroupId(null);
      setTooltip(null);

      map.getTargetElement()?.style.setProperty("cursor", "");
    };

    const target = map.getTargetElement();

    target?.addEventListener("pointerleave", handlePointerLeave);

    // --------------------------------------------------------
    // Resize handling
    // --------------------------------------------------------

    const observer = new ResizeObserver(() => {
      map.updateSize();
    });

    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();

      target?.removeEventListener("pointerleave", handlePointerLeave);

      map.setTarget(undefined);
      map.dispose();

      mapRef.current = null;
      routeSourceRef.current = null;
      airportSourceRef.current = null;

      routeFeaturesRef.current.clear();
      airportFeaturesRef.current.clear();
    };
  }, []);

  // ==========================================================
  // Keep selection available inside event callbacks
  // ==========================================================

  const selectedKeyRef = useRef(selectedKey);
  selectedKeyRef.current = selectedKey;

  // ==========================================================
  // Update route and airport features
  // ==========================================================

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

    const usedAirports = new Set<string>();

    for (const group of groups) {
      const feature = new Feature({
        geometry: new LineString(
          group.coordinates.map((coordinate) => fromLonLat(coordinate)),
        ),
      });

      feature.set("kind", "route");
      feature.set("groupId", group.id);

      feature.setStyle(
        createRouteStyle(
          group.id === selectedGroupId,
          group.id === hoveredGroupId,
        ),
      );

      routeSource.addFeature(feature);

      routeFeaturesRef.current.set(group.id, feature);

      usedAirports.add(group.departure);
      usedAirports.add(group.arrival);
    }

    for (const icao of usedAirports) {
      const airport = airports[icao];

      if (!airport) {
        continue;
      }

      const feature = new Feature({
        geometry: new Point(fromLonLat([airport.longitude, airport.latitude])),
      });

      feature.set("kind", "airport");
      feature.set("icao", icao);

      feature.setStyle(createAirportStyle(false));

      airportSource.addFeature(feature);

      airportFeaturesRef.current.set(icao, feature);
    }
  }, [groups, airports]);

  // ==========================================================
  // Update styles without rebuilding map features
  // ==========================================================

  useEffect(() => {
    for (const [groupId, feature] of routeFeaturesRef.current) {
      feature.setStyle(
        createRouteStyle(
          groupId === selectedGroupId,
          groupId === hoveredGroupId,
        ),
      );
    }

    const selectedGroup = selectedGroupId
      ? groupLookup.get(selectedGroupId)
      : null;

    const selectedAirports = new Set<string>();

    if (selectedGroup) {
      selectedAirports.add(selectedGroup.departure);
      selectedAirports.add(selectedGroup.arrival);
    }

    for (const [icao, feature] of airportFeaturesRef.current) {
      feature.setStyle(createAirportStyle(selectedAirports.has(icao)));
    }
  }, [selectedGroupId, hoveredGroupId, groupLookup]);

  // ==========================================================
  // Focus selected route
  // ==========================================================

  useEffect(() => {
    if (!selectedGroupId) {
      return;
    }

    const map = mapRef.current;

    const feature = routeFeaturesRef.current.get(selectedGroupId);

    const geometry = feature?.getGeometry();

    if (!map || !geometry) {
      return;
    }

    const size = map.getSize();

    if (!size) {
      return;
    }

    const rightPadding = Math.min(
      SELECTED_PADDING[1],
      Math.max(50, size[0] * 0.32),
    );

    map.getView().fit(geometry.getExtent(), {
      size,
      padding: [
        SELECTED_PADDING[0],
        rightPadding,
        SELECTED_PADDING[2],
        SELECTED_PADDING[3],
      ],
      duration: reducedMotion() ? 0 : 850,
      maxZoom: 5,
    });
  }, [selectedGroupId, groups]);

  // ==========================================================
  // Tooltip positioning
  // ==========================================================

  const tooltipStyle = useMemo(() => {
    if (!tooltip) {
      return {};
    }

    const width = containerRef.current?.clientWidth ?? 800;

    const height = containerRef.current?.clientHeight ?? 600;

    const tooltipWidth = 190;
    const tooltipHeight = 65;

    return {
      left: Math.min(
        Math.max(8, tooltip.x + 16),
        Math.max(8, width - tooltipWidth - 8),
      ),
      top: Math.min(
        Math.max(8, tooltip.y - tooltipHeight - 8),
        Math.max(8, height - tooltipHeight - 8),
      ),
    };
  }, [tooltip]);

  // ==========================================================
  // Render
  // ==========================================================

  return (
    <div className="relative h-full min-h-150 w-full overflow-hidden bg-[#090b12]">
      <div ref={containerRef} className="absolute inset-0" />

      {/* Route hover tooltip */}

      {tooltip && (
        <div
          className="pointer-events-none absolute z-30 min-w-40 rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-900 shadow-xl"
          style={tooltipStyle}
        >
          <div className="font-mono font-semibold">
            {tooltip.departure}
            {" → "}
            {tooltip.arrival}
          </div>

          <div className="mt-1 text-[11px] text-zinc-500">
            {tooltip.duration}
            {" · "}
            {tooltip.count} {tooltip.count === 1 ? "flight" : "flights"}
          </div>
        </div>
      )}

      {/* Route legend */}

      <div className="pointer-events-none absolute bottom-5 left-5 z-10 flex flex-wrap items-center gap-4 rounded-lg border border-white/10 bg-[#111217]/90 px-3 py-2 text-[11px] text-zinc-400 shadow-xl backdrop-blur-md">
        <span className="flex items-center gap-2">
          <span className="h-0.5 w-5 bg-[#c75b9e]" />
          Available routes
        </span>

        <span className="flex items-center gap-2">
          <span className="h-0.5 w-5 bg-[#facc15]" />
          Selected route
        </span>

        <span className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-[#0284c7]" />
          Airports
        </span>
      </div>

      {/* Empty state */}

      {routes.length === 0 && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="rounded-xl border border-white/10 bg-[#111217]/90 px-6 py-5 text-center shadow-xl backdrop-blur-md">
            <p className="text-sm font-medium text-zinc-300">
              No routes to display
            </p>

            <p className="mt-2 text-xs text-zinc-500">
              Generate recommendations to display flight paths.
            </p>
          </div>
        </div>
      )}

      {routes.length > 0 && groups.length === 0 && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="rounded-xl border border-white/10 bg-[#111217]/90 px-6 py-5 text-center shadow-xl backdrop-blur-md">
            <p className="text-sm font-medium text-zinc-300">
              Airport coordinates unavailable
            </p>

            <p className="mt-2 text-xs text-zinc-500">
              Route data is available, but the airport locations could not be
              mapped.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
