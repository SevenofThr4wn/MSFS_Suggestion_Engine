import type { Map as MapLibreMap } from "maplibre-gl";

import type { AirportCoordinateLookup } from "@/lib/types/route_finder";

import type { ScoredRecommendation } from "@/lib/types/recommendation";

import { buildRouteGeometry, getRouteCoordinates } from "@/lib/route_map";

import { routeKey } from "@/lib/route_finder";

// ============================================================
// IDs
// ============================================================

export const ROUTE_SOURCE = "flightengine-routes";
export const SELECTED_SOURCE = "flightengine-selected";
export const AIRPORT_SOURCE = "flightengine-airports";

export const ROUTE_LINE_LAYER = "flightengine-route-lines";
export const ROUTE_HIT_LAYER = "flightengine-route-hits";
export const SELECTED_LINE_LAYER = "flightengine-selected-line";
export const AIRPORT_CIRCLE_LAYER = "flightengine-airport-points";
export const AIRPORT_LABEL_LAYER = "flightengine-airport-labels";

// ============================================================
// GeoJSON
// ============================================================

function routeFeatures(
  routes: ScoredRecommendation[],
  airports: AirportCoordinateLookup,
) {
  return routes.flatMap((item) => {
    const coordinates = getRouteCoordinates(item, airports);

    if (!coordinates) {
      return [];
    }

    return [
      {
        type: "Feature" as const,
        properties: {
          routeKey: routeKey(item),
        },
        geometry: buildRouteGeometry(
          coordinates.departure,
          coordinates.arrival,
        ),
      },
    ];
  });
}

function airportFeatures(
  routes: ScoredRecommendation[],
  airports: AirportCoordinateLookup,
) {
  const used = new Set<string>();

  for (const item of routes) {
    const coords = getRouteCoordinates(item, airports);

    if (!coords) {
      continue;
    }

    used.add(coords.departure.icao);
    used.add(coords.arrival.icao);
  }

  return [...used].map((icao) => {
    const airport = airports[icao];

    return {
      type: "Feature" as const,
      properties: {
        icao,
        name: airport.name ?? icao,
      },
      geometry: {
        type: "Point" as const,
        coordinates: [airport.longitude, airport.latitude],
      },
    };
  });
}

// ============================================================
// Layer Initialization
// ============================================================

export function initializeRouteMapLayers(map: MapLibreMap): void {
  if (!map.getSource(ROUTE_SOURCE)) {
    map.addSource(ROUTE_SOURCE, {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: [],
      },
    });
  }

  if (!map.getSource(SELECTED_SOURCE)) {
    map.addSource(SELECTED_SOURCE, {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: [],
      },
    });
  }

  if (!map.getSource(AIRPORT_SOURCE)) {
    map.addSource(AIRPORT_SOURCE, {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: [],
      },
    });
  }

  if (!map.getLayer(ROUTE_LINE_LAYER)) {
    map.addLayer({
      id: ROUTE_LINE_LAYER,
      type: "line",
      source: ROUTE_SOURCE,
      paint: {
        "line-color": "#d946ef",
        "line-width": 1.6,
        "line-opacity": 0.55,
      },
    });
  }

  // Wider invisible hit area makes route selection easier.
  if (!map.getLayer(ROUTE_HIT_LAYER)) {
    map.addLayer({
      id: ROUTE_HIT_LAYER,
      type: "line",
      source: ROUTE_SOURCE,
      paint: {
        "line-color": "#ffffff",
        "line-width": 14,
        "line-opacity": 0,
      },
    });
  }

  if (!map.getLayer(SELECTED_LINE_LAYER)) {
    map.addLayer({
      id: SELECTED_LINE_LAYER,
      type: "line",
      source: SELECTED_SOURCE,
      paint: {
        "line-color": "#facc15",
        "line-width": 3,
        "line-opacity": 1,
      },
    });
  }

  if (!map.getLayer(AIRPORT_CIRCLE_LAYER)) {
    map.addLayer({
      id: AIRPORT_CIRCLE_LAYER,
      type: "circle",
      source: AIRPORT_SOURCE,
      paint: {
        "circle-radius": 4,
        "circle-color": "#facc15",
        "circle-stroke-color": "#101116",
        "circle-stroke-width": 1.5,
      },
    });
  }

  if (!map.getLayer(AIRPORT_LABEL_LAYER)) {
    map.addLayer({
      id: AIRPORT_LABEL_LAYER,
      type: "symbol",
      source: AIRPORT_SOURCE,
      layout: {
        "text-field": ["get", "icao"],
        "text-size": 10,
        "text-offset": [0, 1.5],
        "text-anchor": "top",
        "text-allow-overlap": false,
      },
      paint: {
        "text-color": "#d4d4d8",
        "text-halo-color": "#101116",
        "text-halo-width": 1.5,
      },
    });
  }
}

// ============================================================
// Data Synchronization
// ============================================================

export function updateRouteMapLayers(
  map: MapLibreMap,
  routes: ScoredRecommendation[],
  airports: AirportCoordinateLookup,
  selectedKey: string | null,
): void {
  const all = routeFeatures(routes, airports);

  const selected = selectedKey
    ? all.filter((feature) => feature.properties.routeKey === selectedKey)
    : [];

  const markers = airportFeatures(routes, airports);

  const routeSource = map.getSource(ROUTE_SOURCE) as
    | import("maplibre-gl").GeoJSONSource
    | undefined;

  const selectedSource = map.getSource(SELECTED_SOURCE) as
    | import("maplibre-gl").GeoJSONSource
    | undefined;

  const airportSource = map.getSource(AIRPORT_SOURCE) as
    | import("maplibre-gl").GeoJSONSource
    | undefined;

  routeSource?.setData({
    type: "FeatureCollection",
    features: all,
  });

  selectedSource?.setData({
    type: "FeatureCollection",
    features: selected,
  });

  airportSource?.setData({
    type: "FeatureCollection",
    features: markers,
  });
}
