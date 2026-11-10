import type { AirportCoordinateLookup } from "@/lib/types/route_finder";
import type { ScoredRecommendation } from "@/lib/types/recommendation";

import { getRouteCoordinates } from "@/lib/route_map";
import { routeKey } from "@/lib/route_finder";

export interface GlobeAirport {
  id: string;
  icao: string;
  name: string;
  lat: number;
  lng: number;
}

export interface GlobeRoute {
  id: string;
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  departureIcao: string;
  arrivalIcao: string;
  selected: boolean;
}

export function buildGlobeLayers(
  routes: ScoredRecommendation[],
  airports: AirportCoordinateLookup,
  selectedKey: string | null,
): {
  points: GlobeAirport[];
  arcs: GlobeRoute[];
} {
  const points = new Map<string, GlobeAirport>();
  const arcs: GlobeRoute[] = [];

  for (const item of routes) {
    const coordinates = getRouteCoordinates(item, airports);

    if (!coordinates) continue;

    const departure = coordinates.departure;
    const arrival = coordinates.arrival;

    for (const airport of [departure, arrival]) {
      points.set(airport.icao, {
        id: airport.icao,
        icao: airport.icao,
        name: airport.name ?? airport.icao,
        lat: airport.latitude,
        lng: airport.longitude,
      });
    }

    const id = routeKey(item);

    arcs.push({
      id,
      startLat: departure.latitude,
      startLng: departure.longitude,
      endLat: arrival.latitude,
      endLng: arrival.longitude,
      departureIcao: departure.icao,
      arrivalIcao: arrival.icao,
      selected: id === selectedKey,
    });
  }

  return {
    points: [...points.values()],
    arcs,
  };
}
