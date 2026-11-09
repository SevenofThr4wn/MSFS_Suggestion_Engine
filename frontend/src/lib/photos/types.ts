
export type AircraftPhotoMatch =
  | "registration"
  | "airline_aircraft"
  | "aircraft_type"
  | "none";

export type PhotoConfidence =
  | "high"
  | "medium"
  | "none";

export interface FlightPhotoResult {
  // Photograph
  image_url: string | null;
  source_url: string | null;
  source: string | null;

  // Attribution and licensing
  title: string | null;
  credit: string | null;
  license: string | null;
  license_url: string | null;

  // Aircraft matching
  match_type: AircraftPhotoMatch;
  matched_registration: string | null;
  confidence: PhotoConfidence;

  // Lookup diagnostics
  reason?: string;
}

export interface FlightPhotoIdentity {
  aircraft_icao_code: string | null;
  airline_name: string | null;
  registration: string | null;
  registration_verified: boolean;
}
