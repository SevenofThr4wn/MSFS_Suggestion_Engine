
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type {
  AircraftPredictionRequest,
  HybridAircraftPrediction,
} from "@/lib/types/ml";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

const predictionCache = new Map<string, HybridAircraftPrediction>();

function cacheKey(request: AircraftPredictionRequest): string {
  return [
    request.airline_icao.trim().toUpperCase(),
    request.departure_icao.trim().toUpperCase(),
    request.arrival_icao.trim().toUpperCase(),
    request.distance_nm,
  ].join(":");
}

function getErrorMessage(status: number): string {
  if (status === 503) {
    return "The ML prediction service is unavailable.";
  }

  if (status === 422) {
    return "The flight information is invalid for ML prediction.";
  }

  return `The prediction request failed (${status}).`;
}

export function useAircraftPrediction() {
  const [prediction, setPrediction] =
    useState<HybridAircraftPrediction | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    return () => {
      requestIdRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, []);

  const predict = useCallback(
    async (request: AircraftPredictionRequest): Promise<void> => {
      requestIdRef.current += 1;

      const requestId = requestIdRef.current;

      controllerRef.current?.abort();
      controllerRef.current = null;

      setError(null);
      setPrediction(null);

      const normalized: AircraftPredictionRequest = {
        airline_icao: request.airline_icao.trim().toUpperCase(),
        departure_icao: request.departure_icao.trim().toUpperCase(),
        arrival_icao: request.arrival_icao.trim().toUpperCase(),
        distance_nm: request.distance_nm,
      };

      const key = cacheKey(normalized);
      const cached = predictionCache.get(key);

      if (cached) {
        setPrediction(cached);
        setLoading(false);
        return;
      }

      const controller = new AbortController();

      controllerRef.current = controller;
      setLoading(true);

      try {
        const response = await fetch(
          `${API_BASE_URL}/ml/aircraft/hybrid/predict`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(normalized),
            signal: controller.signal,
            cache: "no-store",
          },
        );

        if (!response.ok) {
          throw new Error(getErrorMessage(response.status));
        }

        const result =
          (await response.json()) as HybridAircraftPrediction;

        if (
          controller.signal.aborted ||
          requestId !== requestIdRef.current
        ) {
          return;
        }

        predictionCache.set(key, result);
        setPrediction(result);
      } catch (caught) {
        if (
          controller.signal.aborted ||
          requestId !== requestIdRef.current
        ) {
          return;
        }

        setError(
          caught instanceof Error
            ? caught.message
            : "Unable to retrieve aircraft predictions.",
        );
      } finally {
        if (requestId === requestIdRef.current) {
          controllerRef.current = null;
          setLoading(false);
        }
      }
    },
    [],
  );

  const cancel = useCallback(() => {
    requestIdRef.current += 1;

    controllerRef.current?.abort();
    controllerRef.current = null;

    setLoading(false);
  }, []);

  return {
    prediction,
    loading,
    error,
    predict,
    cancel,
  };
}
