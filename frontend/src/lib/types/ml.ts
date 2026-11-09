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

export type MLReliability =
  | "low"
  | "moderate"
  | "higher"
  | "unknown";

