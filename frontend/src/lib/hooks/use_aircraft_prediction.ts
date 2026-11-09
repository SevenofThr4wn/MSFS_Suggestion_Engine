"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AircraftPredictionRequest,
  HybridAircraftPrediction,
} from "../types/aircraft";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

const predictionCache = new Map<string, HybridAircraftPrediction>();

function cacheKey(request: AircraftPredictionRequest): string {
  return [
    request.airline_icao,
    request.departure_icao,
    request.arrival_icao,
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
  const [prediction, setPrediction] = useState<HybridAircraftPrediction | null>(
    null,
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  const predict = useCallback(async (request: AircraftPredictionRequest) => {
    controllerRef.current?.abort();

    const key = cacheKey(request);
    const cached = predictionCache.get(key);

    setError(null);

    if (cached) {
      setPrediction(cached);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    controllerRef.current = controller;

    setPrediction(null);
    setLoading(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/ml/aircraft/hybrid/predict`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(request),
          signal: controller.signal,
          cache: "no-store",
        },
      );

      if (!response.ok) {
        throw new Error(getErrorMessage(response.status));
      }

      const result = (await response.json()) as HybridAircraftPrediction;

      if (controller.signal.aborted) return;

      predictionCache.set(key, result);
      setPrediction(result);
    } catch (error: unknown) {
      if (controller.signal.aborted) return;

      setError(
        error instanceof Error
          ? error.message
          : "Unable to retrieve aircraft predictions.",
      );
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
        controllerRef.current = null;
      }
    }
  }, []);

  const cancel = useCallback(() => {
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
