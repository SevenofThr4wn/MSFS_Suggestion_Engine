import { z } from "zod";

export const flightValidationSchema = z
  .object({
    aircraftId: z
      .number({
        error: "Enter a valid aircraft database ID.",
      })
      .int("Aircraft ID must be a whole number.")
      .positive("Aircraft ID must be greater than zero."),

    departure: z
      .string()
      .trim()
      .toUpperCase()
      .regex(/^[A-Z0-9]{4}$/, "Enter a valid 4-character ICAO code."),

    arrival: z
      .string()
      .trim()
      .toUpperCase()
      .regex(/^[A-Z0-9]{4}$/, "Enter a valid 4-character ICAO code."),
  })
  .refine((values) => values.departure !== values.arrival, {
    path: ["arrival"],
    message: "Departure and arrival must differ.",
  });

export type FlightValidationValues = z.infer<typeof flightValidationSchema>;
