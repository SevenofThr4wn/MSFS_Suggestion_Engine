export type MLReliability =
  | "unknown"
  | "low"
  | "moderate"
  | "higher";
  
export interface AircraftPredictionRequest {
  airline_icao: string;
  departure_icao: string;
  arrival_icao: string;
  distance_nm: number;
}

export interface MLVariantSuggestion {
  aircraft_icao: string;
  family_id: string | null;
  family_name: string | null;
  model_score: number;
  matches_predicted_family: boolean;
}

export interface MLFamilyCandidate {
  family_id: string;
  family_name: string;
  model_score: number;
}

export interface HybridAircraftPrediction {
  predicted_family_id: string | null;
  predicted_family_name: string | null;
  predicted_aircraft_icao: string | null;

  family_model_version: string | null;
  variant_model_version: string | null;

  model_agreement: "agree" | "disagree" | "unknown";

  reliability: MLReliability;
  family_reliability: MLReliability;
  variant_reliability: MLReliability;

  suggested_variants: MLVariantSuggestion[];
  family_candidates: MLFamilyCandidate[];

  warnings: string[];
  verified_assignment: boolean;

  prediction_source: string;
  disclaimer: string;

  variant_recommendation_eligible?: boolean;
}

export interface MLAircraftSuggestion {
  aircraft_icao: string;
  family_id: string | null;
  family_name: string | null;
  model_score: number;
  matches_predicted_family: boolean;
}

export interface MLFamilyCandidate {
  family_id: string;
  family_name: string;
  model_score: number;
}

export interface MLHybridPrediction {
  predicted_family_id: string | null;
  predicted_family_name: string | null;

  predicted_aircraft_icao: string | null;

  family_model_version: string | null;
  variant_model_version: string | null;

  model_agreement: "agree" | "disagree" | "unknown";
  reliability: MLReliability;

  family_reliability: MLReliability;
  variant_reliability: MLReliability;

  suggested_variants: MLAircraftSuggestion[];
  family_candidates: MLFamilyCandidate[];

  warnings: string[];

  verified_assignment: boolean;
  prediction_source: string;
  disclaimer: string;
}

// Add these properties to your existing
// recommendation result interface.
export interface MLRecommendationFields {
  ml_prediction: MLHybridPrediction | null;

  ml_status: "available" | "disabled" | "skipped" | "unavailable";
}
