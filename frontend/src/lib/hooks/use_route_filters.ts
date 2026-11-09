"use client";

import { useCallback, useState } from "react";

import type { RouteFinderFilters } from "@/lib/types/route_finder";

// ============================================================
// Default Filters
// ============================================================

export const DEFAULT_ROUTE_FILTERS: RouteFinderFilters = {
  departureCode: "",
  arrivalCode: "",
  aircraftCategory: "",
  airportMode: "main_hubs",
  minDurationHours: 1,
  maxDurationHours: 12,
  ownedOnly: true,
  preferAddonScenery: true,
  includeIndeterminate: false,
  requireRealWorldRoute: false,
  limit: 30,
};

// ============================================================
// Route Filter Hook
// ============================================================

export function useRouteFilters(
  initialFilters: RouteFinderFilters = DEFAULT_ROUTE_FILTERS,
) {
  const [filters, setFilters] = useState<RouteFinderFilters>(() => ({
    ...initialFilters,
  }));

  // ----------------------------------------------------------
  // Update Filters
  // ----------------------------------------------------------

  const updateFilters = useCallback((patch: Partial<RouteFinderFilters>) => {
    setFilters((current) => ({
      ...current,
      ...patch,
    }));
  }, []);

  // ----------------------------------------------------------
  // Reset Filters
  // ----------------------------------------------------------

  const resetFilters = useCallback(() => {
    setFilters({ ...DEFAULT_ROUTE_FILTERS });
  }, []);

  // ----------------------------------------------------------
  // Set All Filters
  // ----------------------------------------------------------

  const replaceFilters = useCallback((next: RouteFinderFilters) => {
    setFilters({ ...next });
  }, []);

  // ----------------------------------------------------------
  // Derived State
  // ----------------------------------------------------------
  const departure = filters.departureCode.trim().toUpperCase();
  const arrival = filters.arrivalCode.trim().toUpperCase();

  const isValid =
  (departure === "" || /^[A-Z]{4}$/.test(departure)) &&
  (arrival === "" || /^[A-Z]{4}$/.test(arrival)) &&
  (departure === "" || arrival === "" || departure !== arrival) &&
  Number.isFinite(filters.minDurationHours) &&
  Number.isFinite(filters.maxDurationHours) &&
  filters.minDurationHours >= 0 &&
  filters.maxDurationHours > 0 &&
  filters.minDurationHours <= filters.maxDurationHours &&
  filters.maxDurationHours <= 30 &&
  Number.isInteger(filters.limit) &&
  filters.limit >= 1 &&
  filters.limit <= 50;

  const hasChanges = (
    Object.keys(DEFAULT_ROUTE_FILTERS) as Array<keyof RouteFinderFilters>
  ).some((key) => filters[key] !== DEFAULT_ROUTE_FILTERS[key]);

  return {
    filters,
    updateFilters,
    resetFilters,
    replaceFilters,

    isValid,
    hasChanges,
  };
}
