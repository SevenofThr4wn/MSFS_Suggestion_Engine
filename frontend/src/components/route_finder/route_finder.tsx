
"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useQuery } from "@tanstack/react-query";

import {
  AlertCircle,
  LoaderCircle,
  Map as MapIcon,
  Table2,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";

import { useRouteFinder } from "@/lib/hooks/use_route_finder";
import { useRouteFilters } from "@/lib/hooks/use_route_filters";
import { useRouteSelection } from "@/lib/hooks/use_route_selection";

import { routeKey } from "@/lib/route_finder";
import {
  fetchAirportCoordinates,
  getRouteCoordinates,
} from "@/lib/route_map";

import type { ScoredRecommendation } from "@/lib/types/recommendation";
import type { RouteFinderView } from "@/lib/types/route_finder";

import SceneryNetwork from "./scenery_network";
import RouteFinderHeader from "./route_finder_header";
import RouteFilterBar from "./route_filter_bar";
import RouteTable from "./route_table";
import RouteMap from "./route_map";
import RouteDetailPanel from "./route_detail_panel";

// ============================================================
// Constants
// ============================================================

const WORKSPACE_HEIGHT = "calc(100vh - 9rem)";

const TOOLBAR_CLASSES = [
  "pointer-events-auto",
  "w-full max-w-6xl",
  "rounded-2xl border border-white/10",
  "bg-[#111217]/95 shadow-2xl",
  "backdrop-blur-xl",
].join(" ");

// ============================================================
// Component
// ============================================================

export default function RouteFinder() {
  // ----------------------------------------------------------
  // UI state
  // ----------------------------------------------------------

  const [view, setView] = useState<RouteFinderView>("map");

  const {
    filters,
    updateFilters,
    resetFilters,
    isValid,
  } = useRouteFilters();

  const {
    data,
    loading,
    error,
    activeRequest,
    generate,
    refresh,
  } = useRouteFinder();

  const {
    selectedKey,
    selectRoute,
    clearSelection,
    getSelectedRoute,
  } = useRouteSelection();

  // ----------------------------------------------------------
  // Recommendation state
  // ----------------------------------------------------------

  const routes = useMemo<ScoredRecommendation[]>(
    () => data?.recommendations ?? [],
    [data],
  );

  const sceneryOnly = filters.preferAddonScenery;

  // The recommendation engine must never run merely
  // because the scenery-only page was opened.
  //
  // If the user switches to recommendation mode,
  // they can explicitly generate recommendations
  // using the existing filter toolbar.

  // ----------------------------------------------------------
  // Selection
  // ----------------------------------------------------------

  const selectedRoute = useMemo(() => {
    if (!selectedKey) {
      return null;
    }

    return getSelectedRoute(routes);
  }, [routes, selectedKey, getSelectedRoute]);

  const effectiveSelectedKey = selectedRoute
    ? routeKey(selectedRoute)
    : null;

  // ----------------------------------------------------------
  // Airport coordinate lookup
  // ----------------------------------------------------------

  const airportCodes = useMemo(() => {
    const codes = new Set<string>();

    for (const item of routes) {
      if (item.route.departure_icao) {
        codes.add(item.route.departure_icao);
      }

      if (item.route.arrival_icao) {
        codes.add(item.route.arrival_icao);
      }
    }

    return [...codes].sort();
  }, [routes]);

  const airportCodeKey = airportCodes.join(",");

  const coordinateQuery = useQuery({
    queryKey: [
      "route-finder",
      "airport-coordinates",
      airportCodeKey,
    ],
    queryFn: ({ signal }) =>
      fetchAirportCoordinates(airportCodes, signal),
    enabled: !sceneryOnly && airportCodes.length > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const airports = useMemo(
    () => coordinateQuery.data ?? {},
    [coordinateQuery.data],
  );

  const selectedCoordinates = useMemo(() => {
    if (!selectedRoute) {
      return null;
    }

    return getRouteCoordinates(selectedRoute, airports);
  }, [selectedRoute, airports]);

  // ----------------------------------------------------------
  // Actions
  // ----------------------------------------------------------

  const handleGenerate = useCallback(() => {
    if (!isValid || sceneryOnly || loading) {
      return;
    }

    clearSelection();
    generate(filters);
  }, [
    isValid,
    sceneryOnly,
    loading,
    clearSelection,
    generate,
    filters,
  ]);

  const handleRefresh = useCallback(() => {
    if (sceneryOnly) {
      return;
    }

    if (activeRequest) {
      clearSelection();
      refresh();
      return;
    }

    if (isValid) {
      generate(filters);
    }
  }, [
    sceneryOnly,
    activeRequest,
    clearSelection,
    refresh,
    isValid,
    generate,
    filters,
  ]);

  const handleSelectRoute = useCallback(
    (route: ScoredRecommendation) => {
      selectRoute(route);
    },
    [selectRoute],
  );

  const handleCloseDetails = useCallback(() => {
    clearSelection();
  }, [clearSelection]);

  const handleSurpriseMe = useCallback(() => {
    if (routes.length === 0) {
      return;
    }

    const suitable = routes.filter(
      (item) =>
        item.route.suitability === "preliminary_pass",
    );

    const pool = suitable.length > 0
      ? suitable
      : routes;

    const randomIndex = Math.floor(
      Math.random() * pool.length,
    );

    selectRoute(pool[randomIndex]);
    setView("map");
  }, [routes, selectRoute]);

  // ----------------------------------------------------------
  // Clear stale selections after recommendation changes
  // ----------------------------------------------------------

  const previousRouteKeysRef = useRef<string | null>(null);

  const routeKeysSignature = useMemo(
    () => routes.map(routeKey).join("|"),
    [routes],
  );

  useEffect(() => {
    const previous = previousRouteKeysRef.current;

    previousRouteKeysRef.current = routeKeysSignature;

    if (
      previous !== null &&
      previous !== routeKeysSignature &&
      selectedKey &&
      !routes.some((route) => routeKey(route) === selectedKey)
    ) {
      clearSelection();
    }
  }, [
    routeKeysSignature,
    routes,
    selectedKey,
    clearSelection,
  ]);

  // ----------------------------------------------------------
  // Statistics
  // ----------------------------------------------------------

  const statistics = useMemo(
    () => ({
      generated: data?.generated_candidates ?? 0,
      evaluated: data?.evaluated_routes ?? 0,
      eligible: data?.eligible_after_filters ?? 0,
      returned: routes.length,
    }),
    [data, routes.length],
  );

  // ----------------------------------------------------------
  // Scenery-only mode
  // ----------------------------------------------------------

  if (sceneryOnly) {
    return (
      <SceneryNetwork
        filters={filters}
        onChange={updateFilters}
        onReset={resetFilters}
      />
    );
  }

  // ==========================================================
  // Render
  // ==========================================================

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col overflow-hidden bg-[#090b12] text-zinc-100">
      {/* ======================================================
          Header
      ====================================================== */}

      <div className="relative z-30 shrink-0">
        <RouteFinderHeader
          loading={loading}
          routeCount={routes.length}
          onRefresh={handleRefresh}
          onSurprise={handleSurpriseMe}
          surpriseDisabled={routes.length === 0}
        />
      </div>

      {/* ======================================================
          Main map workspace
      ====================================================== */}

      <main
        className="relative flex-1 overflow-hidden"
        style={{
          minHeight: WORKSPACE_HEIGHT,
        }}
      >
        {/* Map or table */}

        <div className="absolute inset-0">
          {view === "map" ? (
            <RouteMap
              routes={routes}
              airports={airports}
              selectedKey={effectiveSelectedKey}
              onSelect={handleSelectRoute}
            />
          ) : (
            <div className="h-full overflow-auto bg-[#0b0c10] pt-40">
              <RouteTable
                routes={routes}
                selectedKey={effectiveSelectedKey}
                onSelect={(route) => {
                  handleSelectRoute(route);
                  setView("map");
                }}
              />
            </div>
          )}
        </div>

        {/* ====================================================
            Floating toolbar
        ==================================================== */}

        <div className="pointer-events-none absolute inset-x-0 top-4 z-30 flex justify-center px-4">
          <div className={TOOLBAR_CLASSES}>
            {/* Toolbar summary */}

            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-zinc-500">
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
                    Loading airport locations
                  </span>
                )}
              </div>

              {/* Map/table switcher */}

              <div className="flex items-center rounded-lg border border-white/10 bg-[#0b0c10] p-1">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-pressed={view === "map"}
                  onClick={() => setView("map")}
                  className={[
                    "h-8 gap-2 rounded-md px-3 text-xs",
                    view === "map"
                      ? "bg-amber-400 text-zinc-950 hover:bg-amber-300 hover:text-zinc-950"
                      : "text-zinc-400 hover:bg-white/5 hover:text-white",
                  ].join(" ")}
                >
                  <MapIcon className="size-3.5" />
                  Map
                </Button>

                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-pressed={view === "table"}
                  onClick={() => setView("table")}
                  className={[
                    "h-8 gap-2 rounded-md px-3 text-xs",
                    view === "table"
                      ? "bg-amber-400 text-zinc-950 hover:bg-amber-300 hover:text-zinc-950"
                      : "text-zinc-400 hover:bg-white/5 hover:text-white",
                  ].join(" ")}
                >
                  <Table2 className="size-3.5" />
                  Table
                </Button>
              </div>
            </div>

            {/* Existing FlightEngine filter controls */}

            <div className="[&_form]:rounded-b-2xl [&_form]:border-b-0 [&_form]:bg-transparent [&_form]:px-4 [&_form]:py-3">
              <RouteFilterBar
                filters={filters}
                loading={loading}
                onChange={updateFilters}
                onReset={resetFilters}
                onGenerate={handleGenerate}
              />
            </div>
          </div>
        </div>

        {/* ====================================================
            Error messages
        ==================================================== */}

        {(error || coordinateQuery.isError) && (
          <div className="pointer-events-none absolute inset-x-4 top-44 z-20 mx-auto max-w-2xl">
            <Alert
              variant="destructive"
              className="pointer-events-auto flex items-center gap-3 border-red-500/20 bg-[#211318]/95 text-red-300 shadow-xl backdrop-blur-md"
            >
              <AlertCircle className="size-4 shrink-0" />

              <span className="text-sm">
                {error ??
                  "Unable to retrieve airport coordinates. The route table remains available."}
              </span>
            </Alert>
          </div>
        )}

        {/* ====================================================
            Floating selected-route panel
        ==================================================== */}

        {view === "map" && selectedRoute && (
          <aside className="absolute bottom-5 right-4 top-40 z-20 flex w-[min(380px,calc(100%-32px))] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#101116]/95 shadow-2xl backdrop-blur-xl xl:right-6">
            <div className="flex shrink-0 items-center justify-between border-b border-white/10 bg-[#14161c] px-4 py-3">
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
                  Selected recommendation
                </p>

                <p className="mt-1 font-mono text-xs font-medium text-amber-400">
                  {selectedRoute.route.departure_icao}
                  {" → "}
                  {selectedRoute.route.arrival_icao}
                </p>
              </div>

              <button
                type="button"
                aria-label="Close route details"
                onClick={handleCloseDetails}
                className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-white/10 text-zinc-400 transition-colors hover:bg-white/10 hover:text-white"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              <RouteDetailPanel
                route={selectedRoute}
                coordinates={selectedCoordinates}
              />
            </div>
          </aside>
        )}

        {/* ====================================================
            Loading state
        ==================================================== */}

        {loading && (
          <div className="absolute inset-0 z-40 flex items-center justify-center bg-[#090b12]/65 backdrop-blur-sm">
            <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-[#17191f] px-5 py-4 shadow-2xl">
              <LoaderCircle className="size-5 animate-spin text-amber-400" />

              <span className="text-sm text-zinc-200">
                Generating recommendations...
              </span>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
