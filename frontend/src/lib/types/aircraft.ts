
export type AircraftCategory =
  | "narrow_body"
  | "wide_body"
  | "regional_jet"
  | "turboprop";

export interface AircraftSummary {
  id: number;
  display_name: string;
  icao_code: string | null;
  category: AircraftCategory | null;
  is_owned: boolean;
  cruise_speed_kts: number | null;
  range_nm: number | null;
  takeoff_distance_m: number | null;
  landing_distance_m: number | null;
}
