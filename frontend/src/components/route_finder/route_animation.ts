import type { Map as MapLibreMap } from "maplibre-gl";

import { greatCirclePoints } from "@/lib/route_map";

import type { RouteMapCoordinates } from "@/lib/types/route_finder";

const SOURCE_ID = "flightengine-aircraft-animation";
const LAYER_ID = "flightengine-aircraft-marker";

const DURATION_MS = 7000;

export function initializeRouteAnimation(map: MapLibreMap): void {
  if (!map.getSource(SOURCE_ID)) {
    map.addSource(SOURCE_ID, {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: [],
      },
    });
  }

  if (!map.getLayer(LAYER_ID)) {
    map.addLayer({
      id: LAYER_ID,
      type: "circle",
      source: SOURCE_ID,
      paint: {
        "circle-radius": 6,
        "circle-color": "#facc15",
        "circle-stroke-color": "#111111",
        "circle-stroke-width": 2,
        "circle-opacity": 1,
      },
    });
  }
}

export function animateRoute(
  map: MapLibreMap,
  coordinates: RouteMapCoordinates,
): () => void {
  const source = map.getSource(SOURCE_ID) as
    | import("maplibre-gl").GeoJSONSource
    | undefined;

  if (!source) {
    return () => {};
  }

  const path = greatCirclePoints(
    [coordinates.departure.longitude, coordinates.departure.latitude],
    [coordinates.arrival.longitude, coordinates.arrival.latitude],
    240,
  );

  let frame = 0;
  let startTime: number | null = null;
  let stopped = false;

  const setPosition = (index: number) => {
    source.setData({
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: {},
          geometry: {
            type: "Point",
            coordinates: path[index],
          },
        },
      ],
    });
  };

  // Honour the operating system's reduced-motion preference.
  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;

  if (reducedMotion) {
    setPosition(path.length - 1);
    return () => {
      stopped = true;
    };
  }

  function tick(timestamp: number) {
    if (stopped) {
      return;
    }

    if (startTime === null) {
      startTime = timestamp;
    }

    const elapsed = timestamp - startTime;

    const progress = Math.min(elapsed / DURATION_MS, 1);

    const index = Math.min(
      Math.floor(progress * (path.length - 1)),
      path.length - 1,
    );

    setPosition(index);

    if (progress < 1) {
      frame = requestAnimationFrame(tick);
    }
  }

  frame = requestAnimationFrame(tick);

  return () => {
    stopped = true;
    cancelAnimationFrame(frame);
  };
}
