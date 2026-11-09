
"use client";

import { useCallback, useState } from "react";

import type {
  ScoredRecommendation,
} from "@/lib/types/recommendation";

import { routeKey } from "@/lib/route_finder";

export function useRouteSelection() {
  const [selectedKey, setSelectedKey] = useState<
    string | null
  >(null);

  const selectRoute = useCallback(
    (route: ScoredRecommendation) => {
      setSelectedKey(routeKey(route));
    },
    [],
  );

  const clearSelection = useCallback(() => {
    setSelectedKey(null);
  }, []);

  const getSelectedRoute = useCallback(
    (routes: ScoredRecommendation[]) => {
      if (!selectedKey) {
        return null;
      }

      return (
        routes.find(
          (route) => routeKey(route) === selectedKey,
        ) ?? null
      );
    },
    [selectedKey],
  );

  return {
    selectedKey,
    selectRoute,
    clearSelection,
    getSelectedRoute,
  };
}
