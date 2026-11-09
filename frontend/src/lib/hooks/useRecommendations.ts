"use client";

import { useRef, useState } from "react";

import { sendJson } from "@/lib/api";

import { errorMessage } from "@/lib/utils";

import { validateRecommendation } from "@/lib/schemas/recommendation.schema";
import {
  INITIAL_REQUEST,
  RecommendationRequest,
  RecommendationResponse,
} from "../types/recommendation";

export type UpdateRecommendation = <K extends keyof RecommendationRequest>(
  field: K,
  value: RecommendationRequest[K],
) => void;

export type UpdateAirportFilter = <
  K extends keyof RecommendationRequest["airport_filter"],
>(
  field: K,
  value: RecommendationRequest["airport_filter"][K],
) => void;

function createInitialRequest(): RecommendationRequest {
  return {
    ...INITIAL_REQUEST,
    airport_filter: {
      ...INITIAL_REQUEST.airport_filter,
    },
  };
}

export function useRecommendations() {
  // Legacy form state: retained until all components
  // have migrated to React Hook Form.
  const [form, setForm] = useState<RecommendationRequest>(createInitialRequest);

  const [response, setResponse] = useState<RecommendationResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Prevent overlapping requests without depending
  // on a potentially stale loading state.
  const requestInProgress = useRef(false);

  const update: UpdateRecommendation = (field, value) => {
    setForm((previous) => ({
      ...previous,
      [field]: value,
    }));
  };

  const updateAirport: UpdateAirportFilter = (field, value) => {
    setForm((previous) => ({
      ...previous,
      airport_filter: {
        ...previous.airport_filter,
        [field]: value,
      },
    }));
  };

  async function generate(request?: RecommendationRequest): Promise<void> {
    if (requestInProgress.current) {
      return;
    }

    requestInProgress.current = true;
    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      // New React Hook Form components pass a request.
      // Legacy components can still call generate().
      const source = request ?? form;

      const validated = validateRecommendation(source);

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
  }

  function clearError() {
    setError(null);
  }

  return {
    // Compatibility with current components
    form,
    update,
    updateAirport,

    // API request and response management
    response,
    loading,
    error,
    clearError,
    generate,
  };
}

export type RecommendationsController = ReturnType<typeof useRecommendations>;
