"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";

import { AlertCircle, LoaderCircle, Map, Table2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";

import { useRouteFinder } from "@/lib/hooks/use_route_finder";

import {
  useRouteFilters,
  DEFAULT_ROUTE_FILTERS,
} from "@/lib/hooks/use_route_filters";

import { useRouteSelection } from "@/lib/hooks/use_route_selection";
import { routeKey } from "@/lib/route_finder";
import { fetchAirportCoordinates, getRouteCoordinates } from "@/lib/route_map";
import type { ScoredRecommendation } from "@/lib/types/recommendation";
import type { RouteFinderView } from "@/lib/types/route_finder";
import RouteFinderHeader from "./route_finder_header";
import RouteFilterBar from "./route_filter_bar";
import RouteTable from "./route_table";
import RouteMap from "./route_map";
import RouteDetailPanel from "./route_detail_panel";

// ============================================================
// Route Finder
// ============================================================

export default function RouteFinder() {
  // ----------------------------------------------------------
  // View State
  // ----------------------------------------------------------

  const [view, setView] = useState<RouteFinderView>("table");

  // ----------------------------------------------------------
  // Filter State
  // ----------------------------------------------------------

  const { filters, updateFilters, resetFilters } = useRouteFilters();

  // ----------------------------------------------------------
  // Recommendation Data
  // ----------------------------------------------------------

  const { data, loading, error, generate, refresh } = useRouteFinder();

  // ----------------------------------------------------------
  // Route Selection
  // ----------------------------------------------------------

  const { selectedKey, selectRoute, getSelectedRoute } = useRouteSelection();

  // ----------------------------------------------------------
  // Recommendations
  // ----------------------------------------------------------

  const routes = useMemo<ScoredRecommendation[]>(
    () => data?.recommendations ?? [],
    [data],
  );

  // ----------------------------------------------------------
  // Initial Search
  // ----------------------------------------------------------

  useEffect(() => {
    generate(DEFAULT_ROUTE_FILTERS);
  }, [generate]);

  // ----------------------------------------------------------
  // Selected Route
  // ----------------------------------------------------------

  const selectedRoute = useMemo(() => {
    return getSelectedRoute(routes) ?? routes[0] ?? null;
  }, [routes, getSelectedRoute]);

  const effectiveSelectedKey = selectedRoute ? routeKey(selectedRoute) : null;

  // ==========================================================
  // Airport Coordinate Lookup
  // ==========================================================

  const airportCodes = useMemo(() => {
    const codes = new Set<string>();

    for (const item of routes) {
      codes.add(item.route.departure_icao);
      codes.add(item.route.arrival_icao);
    }

    return [...codes].sort();
  }, [routes]);

  const airportCodeKey = airportCodes.join(",");

  const coordinateQuery = useQuery({
    queryKey: ["route-finder", "airport-coordinates", airportCodeKey],

    queryFn: ({ signal }) => fetchAirportCoordinates(airportCodes, signal),

    enabled: airportCodes.length > 0,

    staleTime: 5 * 60 * 1000,

    gcTime: 30 * 60 * 1000,

    retry: 1,
  });

  const airports = useMemo(
    () => coordinateQuery.data ?? {},
    [coordinateQuery.data],
  );

  // ----------------------------------------------------------
  // Coordinates for Selected Route
  // ----------------------------------------------------------

  const selectedCoordinates = useMemo(() => {
    if (!selectedRoute) {
      return null;
    }

    return getRouteCoordinates(selectedRoute, airports);
  }, [selectedRoute, airports]);

  // ==========================================================
  // Actions
  // ==========================================================

  const handleGenerate = useCallback(() => {
    generate(filters);
  }, [filters, generate]);

  const handleRefresh = useCallback(() => {
    refresh();
  }, [refresh]);

  const handleSurpriseMe = useCallback(() => {
    if (routes.length === 0) {
      return;
    }

    const suitable = routes.filter(
      (item) => item.route.suitability === "preliminary_pass",
    );

    const pool = suitable.length > 0 ? suitable : routes;

    const randomIndex = Math.floor(Math.random() * pool.length);

    selectRoute(pool[randomIndex]);
  }, [routes, selectRoute]);

  // ==========================================================
  // Statistics
  // ==========================================================

  const statistics = {
    generated: data?.generated_candidates ?? 0,
    evaluated: data?.evaluated_routes ?? 0,
    eligible: data?.eligible_after_filters ?? 0,
    returned: routes.length,
  };

  // ==========================================================
  // Render
  // ==========================================================

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col bg-[#0b0c10] text-zinc-100">
      {/* ====================================================
          Header
      ==================================================== */}

      <RouteFinderHeader
        loading={loading}
        routeCount={routes.length}
        onRefresh={handleRefresh}
        onSurprise={handleSurpriseMe}
        surpriseDisabled={routes.length === 0}
      />

      {/* ====================================================
          Filters
      ==================================================== */}

      <RouteFilterBar
        filters={filters}
        loading={loading}
        onChange={updateFilters}
        onReset={resetFilters}
        onGenerate={handleGenerate}
      />

      {/* ====================================================
          Errors
      ==================================================== */}

      {error && (
        <div className="px-6 pt-4">
          <Alert
            variant="destructive"
            className="flex items-center gap-3 border-red-500/20 bg-red-500/5 text-red-300"
          >
            <AlertCircle className="size-4 shrink-0" />
            <span className="text-sm">{error}</span>
          </Alert>
        </div>
      )}

      {coordinateQuery.isError && (
        <div className="px-6 pt-4">
          <Alert
            variant="destructive"
            className="flex items-center gap-3 border-red-500/20 bg-red-500/5 text-red-300"
          >
            <AlertCircle className="size-4 shrink-0" />

            <span className="text-sm">
              Unable to retrieve airport coordinates. The route table remains
              available.
            </span>
          </Alert>
        </div>
      )}

      {/* ====================================================
          Results Toolbar
      ==================================================== */}

      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 px-6 py-3">
        <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-500">
          <span>
            <strong className="text-zinc-300">
              {statistics.generated.toLocaleString()}
            </strong>{" "}
            generated
          </span>

          <span>
            <strong className="text-zinc-300">
              {statistics.evaluated.toLocaleString()}
            </strong>{" "}
            evaluated
          </span>

          <span>
            <strong className="text-zinc-300">
              {statistics.eligible.toLocaleString()}
            </strong>{" "}
            eligible
          </span>

          <span>
            <strong className="text-amber-400">
              {statistics.returned.toLocaleString()}
            </strong>{" "}
            displayed
          </span>

          {coordinateQuery.isFetching && (
            <span className="flex items-center gap-1.5">
              <LoaderCircle className="size-3 animate-spin" />
              Loading locations
            </span>
          )}
        </div>

        {/* ------------------------------------------------
            View Switcher
        ------------------------------------------------ */}

        <div className="flex items-center rounded-lg border border-white/10 bg-zinc-900 p-1">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            aria-pressed={view === "table"}
            onClick={() => setView("table")}
            className={[
              "h-8 gap-2",
              view === "table"
                ? "bg-amber-400 text-zinc-950 hover:bg-amber-300 hover:text-zinc-950"
                : "text-zinc-400 hover:bg-white/5 hover:text-white",
            ].join(" ")}
          >
            <Table2 className="size-4" />
            Table
          </Button>

          <Button
            type="button"
            size="sm"
            variant="ghost"
            aria-pressed={view === "map"}
            onClick={() => setView("map")}
            className={[
              "h-8 gap-2",
              view === "map"
                ? "bg-amber-400 text-zinc-950 hover:bg-amber-300 hover:text-zinc-950"
                : "text-zinc-400 hover:bg-white/5 hover:text-white",
            ].join(" ")}
          >
            <Map className="size-4" />
            Map
          </Button>
        </div>
      </div>

      {/* ====================================================
          Main Content
      ==================================================== */}

      <main className="grid min-h-[650px] flex-1 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px]">
        {/* ------------------------------------------------
            Route Results
        ------------------------------------------------ */}

        <section className="relative min-w-0 overflow-hidden">
          {view === "table" ? (
            <RouteTable
              routes={routes}
              selectedKey={effectiveSelectedKey}
              onSelect={selectRoute}
            />
          ) : (
            <RouteMap
              routes={routes}
              airports={airports}
              selectedKey={effectiveSelectedKey}
              onSelect={selectRoute}
            />
          )}

          {/* ----------------------------------------------
              Recommendation Loading
          ---------------------------------------------- */}

          {loading && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#0b0c10]/75 backdrop-blur-[2px]">
              <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-zinc-900 px-5 py-4 shadow-xl">
                <LoaderCircle className="size-5 animate-spin text-amber-400" />

                <div>
                  <p className="text-sm font-medium text-zinc-200">
                    Generating recommendations
                  </p>

                  <p className="mt-1 text-xs text-zinc-500">
                    Evaluating aircraft, airports and routes...
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ------------------------------------------------
            Selected Flight
        ------------------------------------------------ */}

        <RouteDetailPanel
          route={selectedRoute}
          coordinates={selectedCoordinates}
        />
      </main>
    </div>
  );
}
