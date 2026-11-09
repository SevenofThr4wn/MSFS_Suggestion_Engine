export type FlightCategory = "VFR" | "MVFR" | "IFR" | "LIFR";

export interface WeatherContext {
  icao: string;
  available: boolean;

  category: FlightCategory | null;

  wind_speed_kt: number | null;
  visibility_mi: number | null;

  observation_time: string | null;
  raw: string | null;

  warnings: string[];
}
