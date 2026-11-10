
"use client";

import { useEffect, useRef, useState } from "react";
import { MapPinned } from "lucide-react";

import "ol/ol.css";

import Map from "ol/Map";
import View from "ol/View";
import TileLayer from "ol/layer/Tile";
import VectorLayer from "ol/layer/Vector";
import XYZ from "ol/source/XYZ";
import VectorSource from "ol/source/Vector";
import Feature from "ol/Feature";
import Point from "ol/geom/Point";
import LineString from "ol/geom/LineString";
import { Circle as CircleStyle, Fill, Stroke, Style } from "ol/style";
import { fromLonLat } from "ol/proj";
import { defaults as defaultControls } from "ol/control";

import type { RouteMapCoordinates } from "@/lib/types/route_finder";
import { greatCirclePoints } from "@/lib/route_map";

interface RoutePreviewMapProps {
  coordinates?: RouteMapCoordinates | null;
  height?: number;
}

function validCoordinates(
  coordinates: RouteMapCoordinates | null | undefined,
): coordinates is RouteMapCoordinates {
  if (!coordinates) return false;

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
    if (
      !hasCoordinates ||
      !containerRef.current ||
      departureLat === undefined ||
      departureLon === undefined ||
      arrivalLat === undefined ||
      arrivalLon === undefined
    ) {
      return;
    }

    const departure: [number, number] = [
      departureLon,
      departureLat,
    ];

    const arrival: [number, number] = [
      arrivalLon,
      arrivalLat,
    ];

    const path = greatCirclePoints(departure, arrival, 96);

    // Unwrap longitudes so a Pacific route does not
    // incorrectly cross the entire flat map.
    const unwrapped: [number, number][] = [];

    for (const [lng, lat] of path) {
      const previous = unwrapped.at(-1);

      const adjustedLng = previous
        ? lng + 360 * Math.round((previous[0] - lng) / 360)
        : lng;

      unwrapped.push([adjustedLng, lat]);
    }

    const projectedPath = unwrapped.map((point) =>
      fromLonLat(point),
    );

    const line = new Feature({
      geometry: new LineString(projectedPath),
    });

    line.setStyle(
      new Style({
        stroke: new Stroke({
          color: "#d946ef",
          width: 2.5,
        }),
      }),
    );

    const departurePoint = new Feature({
      geometry: new Point(projectedPath[0]),
    });

    const arrivalPoint = new Feature({
      geometry: new Point(projectedPath[projectedPath.length - 1]),
    });

    const pointStyle = new Style({
      image: new CircleStyle({
        radius: 5,
        fill: new Fill({
          color: "#facc15",
        }),
        stroke: new Stroke({
          color: "#111217",
          width: 2,
        }),
      }),
    });

    departurePoint.setStyle(pointStyle);
    arrivalPoint.setStyle(pointStyle);

    const source = new VectorSource({
      features: [line, departurePoint, arrivalPoint],
    });

    const vectorLayer = new VectorLayer({
      source,
    });

    const tileLayer = new TileLayer({
      source: new XYZ({
        url: `https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png?key=${encodeURIComponent(process.env.NEXT_PUBLIC_CARTO_API_KEY ?? "")}`,
        attributions:
          '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · © <a href="https://carto.com/attributions">CARTO</a>',
        crossOrigin: "anonymous",
      }),
    });

    const map = new Map({
      target: containerRef.current,
      layers: [tileLayer, vectorLayer],
      view: new View({
        center: projectedPath[0],
        zoom: 2,
        minZoom: 1,
        maxZoom: 12,
        multiWorld: true,
      }),
      controls: defaultControls({
        zoom: false,
        rotate: false,
      }),
      interactions: [],
    });

    const geometry = line.getGeometry();

    if (geometry) {
      map.getView().fit(geometry.getExtent(), {
        size: map.getSize(),
        padding: [30, 30, 30, 30],
        duration: 0,
        maxZoom: 6,
      });
    }

    const handleTileError = () => {
      setError("Unable to load map tiles.");
    };

    tileLayer.getSource()?.on("tileloaderror", handleTileError);

    return () => {
      tileLayer.getSource()?.un("tileloaderror", handleTileError);
      map.setTarget(undefined);
      map.dispose();
    };
  }, [
    hasCoordinates,
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

          <p className="mt-1 text-[11px] text-zinc-600">
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
      <div
        ref={containerRef}
        className="absolute inset-0"
      />

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#17191f]/95 px-5 text-center">
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      <div className="pointer-events-none absolute bottom-2 left-2 rounded-md bg-black/70 px-2 py-1 font-mono text-[10px] text-zinc-200">
        {departureIcao} → {arrivalIcao}
      </div>
    </div>
  );
}
