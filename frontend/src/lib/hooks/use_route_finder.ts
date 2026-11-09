"use client";

import { useCallback, useState } from "react";

import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { fetchRecommendations } from "@/lib/route_finder";

import type { RouteFinderFilters } from "@/lib/types/route_finder";

const QUERY_KEY = ["route-finder", "recommendations"] as const;

export function useRouteFinder() {
  const queryClient = useQueryClient();

  const [activeRequest, setActiveRequest] = useState<RouteFinderFilters | null>(
    null,
  );

  const queryKey = [...QUERY_KEY, activeRequest] as const;

  // --------------------------------------------------------
  // Recommendation Query
  // --------------------------------------------------------

  const query = useQuery({
    queryKey,

    queryFn: ({ signal }) => {
      if (!activeRequest) {
        throw new Error("No route search has been configured.");
      }

      return fetchRecommendations(activeRequest, signal);
    },

    enabled: activeRequest !== null,

    staleTime: 60_000,

    gcTime: 300_000,

    retry: 1,

    refetchOnWindowFocus: false,

    placeholderData: keepPreviousData,
  });

  // --------------------------------------------------------
  // Generate Recommendations
  // --------------------------------------------------------

  const generate = useCallback(
    (filters: RouteFinderFilters) => {
      const nextRequest = {
        ...filters,
      };

      setActiveRequest(nextRequest);

      // Invalidate this search so clicking Generate
      // again also refreshes an identical request.
      void queryClient.invalidateQueries({
        queryKey: [...QUERY_KEY, nextRequest],
        exact: true,
      });
    },
    [queryClient],
  );

  // --------------------------------------------------------
  // Refresh Current Search
  // --------------------------------------------------------

  const refresh = useCallback(() => {
    if (!activeRequest) {
      return;
    }

    void queryClient.invalidateQueries({
      queryKey,
      exact: true,
    });
  }, [activeRequest, queryClient, queryKey]);

  // --------------------------------------------------------
  // Clear Current Search
  // --------------------------------------------------------

  const clear = useCallback(() => {
    setActiveRequest(null);
  }, []);

  // --------------------------------------------------------
  // Derived Query State
  // --------------------------------------------------------

  const loading = query.isFetching;

  const error = query.error instanceof Error ? query.error.message : null;

  return {
    data: query.data ?? null,

    loading,
    error,

    activeRequest,

    generate,
    refresh,
    clear,

    isPending: query.isPending,
    isFetching: query.isFetching,
    isSuccess: query.isSuccess,
    isError: query.isError,
  };
}
