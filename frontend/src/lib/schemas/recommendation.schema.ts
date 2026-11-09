import { z } from "zod";
import { INITIAL_REQUEST, RecommendationRequest } from "../types/recommendation";



const airportCode = z
  .string()
  .trim()
  .toUpperCase()
  .regex(/^[A-Z0-9]{3,4}$/, "Enter a valid 3–4 character airport code.");

const optionalAirportCode = z.union([airportCode, z.literal(""), z.null()]);

const airportFilterSchema = z.object({
  minimum_airport_size: z
    .enum(["small_airport", "medium_airport", "large_airport"])
    .nullable(),

  require_paved_runway: z.boolean(),
  require_known_runway_data: z.boolean(),
  require_scheduled_service: z.boolean(),
});

export const recommendationSchema = z
  .object({
    mode: z.literal("discovery"),

    departure_code: airportCode,
    arrival_code: optionalAirportCode,

    prefer_addon_scenery: z.boolean(),

    aircraft_id: z.number().int().positive().nullable(),
    preferred_category: z.string().nullable(),

    owned_only: z.boolean(),

    min_duration_hours: z.number().min(0.5).max(24),
    max_duration_hours: z.number().min(1).max(30),

    max_airports: z.number().int().min(10).max(10000),
    max_candidates: z.number().int().min(10).max(100000),

    include_indeterminate: z.boolean(),
    require_real_world_route: z.boolean(),

    limit: z.number().int().min(1).max(100),

    airport_filter: airportFilterSchema,

    airport_mode: z.enum(["all", "commercial", "major", "main_hubs"]),

    min_flyability_score: z.number().min(0).max(100),

    live_weather: z.boolean(),
    scenarios_enabled: z.boolean(),
    require_real_world_service: z.boolean(),
    strict_aircraft_category: z.boolean(),
    include_decision_trace: z.boolean(),
    include_rejected_examples: z.boolean(),
    departure_gate_enabled: z.boolean(),
    departure_date: z.string().nullable(),
    schedule_enabled: z.boolean(),
    require_scheduled_service: z.boolean(),
    prefer_scheduled_aircraft: z.boolean(),

    weather_preference: z.enum(["any", "fair", "challenging"]),
  })
  .superRefine((value, context) => {
    if (value.min_duration_hours >= value.max_duration_hours) {
      context.addIssue({
        code: "custom",
        path: ["max_duration_hours"],
        message: "Maximum duration must exceed minimum duration.",
      });
    }

    if (value.arrival_code && value.departure_code === value.arrival_code) {
      context.addIssue({
        code: "custom",
        path: ["arrival_code"],
        message: "Departure and arrival airports must differ.",
      });
    }
  });

export type RecommendationFormValues = z.input<typeof recommendationSchema>;

export type ValidatedRecommendation = z.output<typeof recommendationSchema>;

export const RECOMMENDATION_DEFAULT_VALUES: RecommendationRequest = {
  ...INITIAL_REQUEST,
  departure_date: null,
  schedule_enabled: false,
  require_scheduled_service: false,
  prefer_scheduled_aircraft: false,
  airport_filter: {
    ...INITIAL_REQUEST.airport_filter,
  },
};

export function validateRecommendation(
  values: RecommendationFormValues,
): RecommendationRequest {
  const parsed = recommendationSchema.parse(values);

  return {
    ...parsed,
    arrival_code: parsed.arrival_code || null,
  };
}
