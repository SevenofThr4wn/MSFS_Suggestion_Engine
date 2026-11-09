
export type RouteSuitability =
  | "preliminary_pass"
  | "indeterminate"
  | "rejected";

export type RouteDistanceSource =
  | "stored_route"
  | "great_circle";

export interface RouteRecommendation {
  route_id: number | null;

  // Departure
  departure_icao: string;
  departure_name: string;

  // Arrival
  arrival_icao: string;
  arrival_name: string;

  // Aircraft
  aircraft_id: number;
  aircraft_name: string;
  aircraft_icao_code: string | null;

  // Airline and flight information
  airline_name: string | null;
  airline_icao: string | null;
  flight_number: string | null;
  is_real_world_route: boolean;

  // Flight details
  distance_nm: number;
  distance_source?: RouteDistanceSource;

  estimated_duration_min: number;
  duration_source?: string;

  // Suitability
  suitability: RouteSuitability;

  // Scoring
  score: number;
  score_breakdown?: Record<string, number>;

  registration?: string | null;
  registration_verified?: boolean;

flyability_status?: "estimated" | "personalized";
flyability_breakdown?: Record<string, number>;
flyability_evidence?: Record<string, boolean>;
personal_feedback_available?: boolean;

  flyability_score: number;

  // Explanations
  reasons: string[];
  warnings: string[];
}
