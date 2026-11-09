"use client";

import { useRef, useState } from "react";
import { sendJson } from "@/lib/api";


import {
  flightValidationSchema,
  type FlightValidationValues,
} from "@/lib/schemas/flight-validation.schema";

import { errorMessage } from "@/lib/utils";
import { ValidationResponse } from "../types/validation";

export const INITIAL_VALIDATION_VALUES: FlightValidationValues = {
  aircraftId: 5,
  departure: "KJFK",
  arrival: "TFFJ",
};

export function useFlightValidation() {
  const [result, setResult] = useState<ValidationResponse | null>(null);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const requestInProgress = useRef(false);

  async function validate(values: FlightValidationValues): Promise<void> {
    if (requestInProgress.current) return;

    requestInProgress.current = true;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const validated = flightValidationSchema.parse(values);

      const data = await sendJson<ValidationResponse>(
        "/api/recommendations/validate",
        {
          aircraft_id: validated.aircraftId,
          departure_code: validated.departure,
          arrival_code: validated.arrival,
          require_paved: true,
        },
      );

      setResult(data);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      requestInProgress.current = false;
      setLoading(false);
    }
  }

  function clearError() {
    setError(null);
  }

  return {
    result,
    loading,
    error,
    clearError,
    validate,
  };
}

export type ValidationController = ReturnType<typeof useFlightValidation>;
