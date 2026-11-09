export type ValidationStatus =
  | "preliminary_pass"
  | "indeterminate"
  | "rejected";

export type ValidationSeverity = "reject" | "unknown";

export interface ValidationIssue {
  code: string;
  severity: ValidationSeverity;
  airport_icao: string | null;
  message: string;

  observed: number | string | null;
  required: number | string | null;
  unit: string | null;
}

export interface ValidationOutcome {
  status: ValidationStatus;

  issues: ValidationIssue[];

  departure_runway: string | null;
  arrival_runway: string | null;
}

export interface GateSuggestion {
  airport_icao: string;
  gate: string | null;

  status: "candidate" | "unknown";
  source: string;
  reasons: string[];
}

export interface AirportCompatibility {
  airport_icao: string;
  aircraft_id: number;

  operation: "takeoff" | "landing";

  status: ValidationStatus;

  selected_runway: string | null;

  reasons: string[];
  warnings: string[];
}

export type AddonCompatibilityStatus = "available" | "unavailable" | "unknown";

export type AddonCompatibilityCategory =
  | "aircraft"
  | "departure_scenery"
  | "arrival_scenery"
  | "livery"
  | "gsx_departure"
  | "gsx_arrival";

export interface AddonCompatibilityCheck {
  category: AddonCompatibilityCategory;
  label: string;
  status: AddonCompatibilityStatus;

  description?: string | null;
  addonName?: string | null;
  source?: string | null;
}

export interface RouteAddonCompatibility {
  checks: AddonCompatibilityCheck[];
  verifiedAt?: string | null;
}
