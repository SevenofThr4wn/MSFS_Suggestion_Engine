import type { AircraftCategory } from "./aircraft";

import type { AirportMode } from "./airport";

export interface RouteFinderFilters {
  departureCode: string;
  arrivalCode: string;

  aircraftCategory: AircraftCategory | "";
  airportMode: AirportMode;

  minDurationHours: number;
  maxDurationHours: number;

  ownedOnly: boolean;
  preferAddonScenery: boolean;
  includeIndeterminate: boolean;
  requireRealWorldRoute: boolean;

  limit: number;
}

export type RouteSortKey =
  | "route"
  | "aircraft"
  | "duration"
  | "flyability"
  | "score";

export type SortDirection = "asc" | "desc";
export type RouteFinderStatus = "idle" | "loading" | "success" | "error";

export interface RouteMapCoordinate {
  latitude: number;
  longitude: number;
}

export interface RouteMapAirport extends RouteMapCoordinate {
  icao: string;
  name?: string;
}

export interface RouteMapCoordinates {
  departure: RouteMapAirport;
  arrival: RouteMapAirport;
}



export interface RouteMapCoordinate {
  latitude: number;
  longitude: number;
}

export interface RouteMapAirport extends RouteMapCoordinate {
  icao: string;
  name?: string;
}

export interface RouteMapCoordinates {
  departure: RouteMapAirport;
  arrival: RouteMapAirport;
}

export interface AirportCoordinateResponse {
  airports: RouteMapAirport[];
  missing: string[];
}

export type AirportCoordinateLookup =
  Record<string, RouteMapAirport>;

export type RouteFinderView = "table" | "map";
