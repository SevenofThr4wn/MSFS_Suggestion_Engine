
import type { RouteRecommendation } from "./route";
import type { ValidationOutcome, GateSuggestion } from "./validation";
import type { AirportLocation } from "./airport";

export type {
  RecommendationRequest,
} from "@/lib/schemas/recommendation.schema";

export interface ScoredRecommendation {
  route: RouteRecommendation;

  arrival_location?: AirportLocation | null;

  final_score: number;
  preference_score: number;
  flyability_score: number;

  realism_score: number | null;
  weather_score: number | null;
  history_novelty_score: number | null;

  score_breakdown?: Record<string, number>;
  evidence_coverage?: Record<string, boolean>;

  aircraft_validation?: ValidationOutcome | null;
  departure_gate?: GateSuggestion | null;

  reasons: string[];
  warnings?: string[];
}

export type Recommendation = ScoredRecommendation;

export interface DecisionTrace {
  request_id?: string | null;
  events?: unknown[];
  [key: string]: unknown;
}

export interface RecommendationResponse {
  engine?: string;
  request_id?: string | null;

  departure_location?: AirportLocation | null;

  generated_candidates: number;
  evaluated_routes: number;
  eligible_after_filters: number;
  returned: number;

  recommendations: ScoredRecommendation[];

  warnings: string[];
  rejected_examples?: unknown[];
  decision_trace?: DecisionTrace | null;
}
