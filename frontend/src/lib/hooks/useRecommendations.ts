"use client";

import { useCallback, useRef, useState } from "react";

import { sendJson } from "@/lib/api";
import { errorMessage } from "@/lib/utils";

import {
  recommendationSchema,
  validateRecommendation,
} from "@/lib/schemas/recommendation.schema";

import type { RecommendationResponse } from "@/lib/types/recommendation";

export function useRecommendations() {
  const [response, setResponse] = useState<RecommendationResponse | null>(null);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const requestInProgress = useRef(false);

  const generate = useCallback(async (request: unknown): Promise<void> => {
    if (requestInProgress.current) {
      return;
    }

    requestInProgress.current = true;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      // Validate unknown input before passing it
      // to the API request.
      const parsed = recommendationSchema.parse(request);

      const validated = validateRecommendation(parsed);

      const result = await sendJson<RecommendationResponse>(
        "/api/recommendations/generate",
        validated,
      );

      setResponse(result);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      requestInProgress.current = false;
      setLoading(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const clearResults = useCallback(() => {
    setResponse(null);
  }, []);

  return {
    response,
    loading,
    error,
    generate,
    clearError,
    clearResults,
  };
}

export type RecommendationsController = ReturnType<typeof useRecommendations>;
