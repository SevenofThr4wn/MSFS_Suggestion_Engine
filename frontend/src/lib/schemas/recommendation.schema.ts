
import { z } from "zod";

const airportCode = z
  .string()
  .trim()
  .toUpperCase()
  .regex(/^[A-Z0-9]{3,4}$/, "Enter a valid 3–4 character airport code.");

const optionalAirportCode = z.union([
  airportCode,
  z.literal(""),
  z.null(),
]);

const airportFilterSchema = z.object({
  minimum_airport_size: z
    .enum(["small_airport", "medium_airport", "large_airport"])
    .nullable(),

  require_paved_runway: z.boolean().nullable(),
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

    min_duration_hours: z.number().min(0).max(30),
    max_duration_hours: z.number().positive().max(30),

    max_airports: z.number().int().min(2).max(500),
    max_candidates: z.number().int().min(1).max(20000),

    include_indeterminate: z.boolean(),
    require_real_world_route: z.boolean(),

    limit: z.number().int().min(1).max(50),

    airport_filter: airportFilterSchema,

    airport_mode: z.enum([
      "all",
      "commercial",
      "major",
      "main_hubs",
    ]),

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

    weather_preference: z.enum([
      "any",
      "fair",
      "challenging",
    ]),
  })
  .superRefine((values, context) => {
    if (values.min_duration_hours > values.max_duration_hours) {
      context.addIssue({
        code: "custom",
        path: ["max_duration_hours"],
        message: "Maximum duration must be at least the minimum duration.",
      });
    }

    if (
      values.arrival_code &&
      values.departure_code === values.arrival_code
    ) {
      context.addIssue({
        code: "custom",
        path: ["arrival_code"],
        message: "Departure and arrival airports must differ.",
      });
    }

    if (values.require_real_world_route) {
      context.addIssue({
        code: "custom",
        path: ["require_real_world_route"],
        message:
          "Real-world route verification requires database mode.",
      });
    }
  });

export type RecommendationFormValues =
  z.input<typeof recommendationSchema>;

export type ValidatedRecommendation =
  z.output<typeof recommendationSchema>;

export type RecommendationRequest = RecommendationFormValues;

export const RECOMMENDATION_DEFAULT_VALUES: RecommendationRequest = {
  mode: "discovery",

  departure_code: "OMDB",
  arrival_code: null,

  prefer_addon_scenery: true,

  aircraft_id: null,
  preferred_category: null,
  owned_only: true,

  min_duration_hours: 2,
  max_duration_hours: 6,

  max_airports: 100,
  max_candidates: 2500,

  include_indeterminate: false,
  require_real_world_route: false,

  limit: 10,

  airport_filter: {
    minimum_airport_size: null,
    require_paved_runway: null,
    require_known_runway_data: false,
    require_scheduled_service: false,
  },

  airport_mode: "major",
  min_flyability_score: 0,

  live_weather: false,
  scenarios_enabled: false,

  require_real_world_service: false,
  strict_aircraft_category: true,

  include_decision_trace: false,
  include_rejected_examples: true,
  departure_gate_enabled: true,

  departure_date: null,

  schedule_enabled: false,
  require_scheduled_service: false,
  prefer_scheduled_aircraft: true,

  weather_preference: "any",
};

export function validateRecommendation(
  values: RecommendationFormValues,
): ValidatedRecommendation {
  const parsed = recommendationSchema.parse(values);

  return {
    ...parsed,
    arrival_code: parsed.arrival_code || null,
  };
}
