"use client";

import { useCallback, useRef, useState } from "react";

import { sendJson } from "@/lib/api";
import { errorMessage } from "@/lib/utils";

import {
  flightValidationSchema,
  type FlightValidationValues,
} from "@/lib/schemas/flight-validation.schema";

import type { ValidationResponse } from "@/lib/types/validation";

export function useFlightValidation() {
  const [result, setResult] = useState<ValidationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requestInProgress = useRef(false);

  const validate = useCallback(
    async (values: FlightValidationValues): Promise<void> => {
      if (requestInProgress.current) {
        return;
      }

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
    },
    [],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const clearResult = useCallback(() => {
    setResult(null);
  }, []);

  return {
    result,
    loading,
    error,
    validate,
    clearError,
    clearResult,
  };
}

export type ValidationController = ReturnType<typeof useFlightValidation>;
