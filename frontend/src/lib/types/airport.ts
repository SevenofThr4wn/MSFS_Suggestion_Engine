export type AirportMode =
  | "all"
  | "major"
  | "main_hubs"
  | "commercial";

export interface AirportCoordinates {
  latitude: number;
  longitude: number;
}

export interface AirportSummary {
  icao_code: string;
  iata_code: string | null;
  name: string;

  city: string | null;
  country: string | null;

  latitude: number;
  longitude: number;

  airport_type: string | null;
  scheduled_service: boolean | null;
  has_addon_scenery: boolean;
}

export interface AirportLocation {
  icao: string;
  airport_name: string | null;
  city: string | null;
  region: string | null;
  country: string | null;
  display_name: string;
}