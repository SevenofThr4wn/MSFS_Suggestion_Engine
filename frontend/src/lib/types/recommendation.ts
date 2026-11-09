import type { RouteRecommendation } from "./route";
import type { ValidationOutcome, GateSuggestion } from "./validation";

export interface ScoredRecommendation {
  route: RouteRecommendation;

  // Scoring
  final_score: number;
  preference_score: number;
  flyability_score: number;

  realism_score: number | null;
  weather_score: number | null;
  history_novelty_score: number | null;

  score_breakdown?: Record<string, number>;

  // Validation
  aircraft_validation?: ValidationOutcome | null;

  // Airport operations
  departure_gate?: GateSuggestion | null;

  // Supporting evidence
  reasons: string[];
  warnings?: string[];

  evidence_coverage?: Record<string, unknown>;
}

export interface RecommendationResponse {
  recommendations: ScoredRecommendation[];

  // Processing statistics
  generated_candidates: number;
  evaluated_routes: number;
  eligible_after_filters: number;
  returned: number;

  // Diagnostics
  warnings?: string[];
  rejected_examples?: unknown[];
}

export interface RecommendationRequest {
  mode: "discovery" | "point-to-point" | "database";

  departure_code: string;
  arrival_code?: string | null;

  min_duration_hours: number;
  max_duration_hours: number;

  preferred_category?: string | null;

  owned_only: boolean;
  prefer_addon_scenery: boolean;

  airport_mode: string;

  limit: number;
  max_candidates: number;

  include_indeterminate: boolean;
  require_real_world_route: boolean;

  live_weather?: boolean;
  scenarios_enabled?: boolean;

  include_decision_trace?: boolean;
  include_rejected_examples?: boolean;
  departure_gate_enabled?: boolean;
}
