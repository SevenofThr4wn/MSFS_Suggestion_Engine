import { z } from "zod";

import type { EditableFeedback } from "@/lib/hooks/useFlightFeedback";

const rating = z.number().int().min(1).max(5);

export const flightFeedbackSchema = z.object({
  enjoyment_rating: rating,
  scenery_rating: rating,
  approach_rating: rating,
  airport_experience_rating: rating,
  aircraft_enjoyment_rating: rating,

  would_fly_again: z.enum(["yes", "maybe", "no"]),

  notes: z.string().max(2000),
});

export type FlightFeedbackValues = z.infer<typeof flightFeedbackSchema>;

export function toEditableFeedback(
  values: FlightFeedbackValues,
): EditableFeedback {
  return {
    enjoyment_rating: values.enjoyment_rating,
    scenery_rating: values.scenery_rating,
    approach_rating: values.approach_rating,
    airport_experience_rating: values.airport_experience_rating,
    aircraft_enjoyment_rating: values.aircraft_enjoyment_rating,
    would_fly_again: values.would_fly_again,
    notes: values.notes,
  };
}
