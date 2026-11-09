"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowDownUp, ArrowUp, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ScoredRecommendation } from "@/lib/types/recommendation";
import type { RouteSortKey, SortDirection } from "@/lib/types/route_finder";
import { routeKey } from "@/lib/route_finder";
import RouteTableRow from "./route_table_row";

// ============================================================
// Types
// ============================================================

interface RouteTableProps {
  routes: ScoredRecommendation[];
  selectedKey: string | null;

  onSelect: (route: ScoredRecommendation) => void;
}

interface SortableHeaderProps {
  label: string;
  column: RouteSortKey;

  activeColumn: RouteSortKey;
  direction: SortDirection;

  align?: "left" | "right";

  onSort: (column: RouteSortKey) => void;
}

// ============================================================
// Sorting
// ============================================================

function compareNumbers(first: number, second: number): number {
  return first - second;
}

function compareRoutes(
  first: ScoredRecommendation,
  second: ScoredRecommendation,
  column: RouteSortKey,
): number {
  const a = first.route;
  const b = second.route;

  switch (column) {
    case "route":
      return `${a.departure_icao}-${a.arrival_icao}`.localeCompare(
        `${b.departure_icao}-${b.arrival_icao}`,
      );

    case "aircraft":
      return a.aircraft_name.localeCompare(b.aircraft_name);

    case "duration":
      return compareNumbers(a.estimated_duration_min, b.estimated_duration_min);

    case "flyability":
      return compareNumbers(a.flyability_score, b.flyability_score);

    case "score":
      return compareNumbers(first.final_score, second.final_score);

    default:
      return 0;
  }
}

// ============================================================
// Sortable Column Header
// ============================================================

function SortableHeader({
  label,
  column,
  activeColumn,
  direction,
  align = "left",
  onSort,
}: SortableHeaderProps) {
  const active = column === activeColumn;

  const SortIcon = active
    ? direction === "asc"
      ? ArrowUp
      : ArrowDown
    : ArrowDownUp;

  const ariaSort = !active
    ? "none"
    : direction === "asc"
      ? "ascending"
      : "descending";

  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={[
        "whitespace-nowrap px-4 py-3",
        align === "right" ? "text-right" : "text-left",
      ].join(" ")}
    >
      <button
        type="button"
        onClick={() => onSort(column)}
        className={[
          "inline-flex items-center gap-1.5",
          "rounded-sm text-[11px] font-semibold",
          "uppercase tracking-wider transition-colors",
          "outline-none focus-visible:ring-2",
          "focus-visible:ring-amber-400",
          active ? "text-amber-400" : "text-zinc-500 hover:text-zinc-200",
        ].join(" ")}
      >
        {label}

        <SortIcon className="size-3.5" />
      </button>
    </th>
  );
}

// ============================================================
// Route Table
// ============================================================

export default function RouteTable({
  routes,
  selectedKey,
  onSelect,
}: RouteTableProps) {
  const [sortKey, setSortKey] = useState<RouteSortKey>("score");

  const [direction, setDirection] = useState<SortDirection>("desc");

  // ----------------------------------------------------------
  // Sorted Recommendations
  // ----------------------------------------------------------

  const sortedRoutes = useMemo(() => {
    const sorted = [...routes];

    sorted.sort((first, second) => {
      const comparison = compareRoutes(first, second, sortKey);

      if (comparison !== 0) {
        return direction === "asc" ? comparison : -comparison;
      }

      // Stable deterministic ordering when scores match.
      return routeKey(first).localeCompare(routeKey(second));
    });

    return sorted;
  }, [routes, sortKey, direction]);

  // ----------------------------------------------------------
  // Change Sorting
  // ----------------------------------------------------------

  function handleSort(column: RouteSortKey) {
    if (column === sortKey) {
      setDirection((current) => (current === "asc" ? "desc" : "asc"));

      return;
    }

    setSortKey(column);

    setDirection(
      column === "score" || column === "flyability" ? "desc" : "asc",
    );
  }

  // ----------------------------------------------------------
  // Empty State
  // ----------------------------------------------------------

  if (routes.length === 0) {
    return (
      <div className="flex min-h-125 flex-col items-center justify-center gap-4 px-6 text-center">
        <div className="flex size-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.035]">
          <SearchX className="size-6 text-zinc-500" />
        </div>

        <div>
          <h3 className="text-sm font-semibold text-zinc-200">
            No routes found
          </h3>

          <p className="mt-2 max-w-sm text-xs leading-5 text-zinc-500">
            Try adjusting your departure airport, flight duration, aircraft
            category or eligibility requirements.
          </p>
        </div>
      </div>
    );
  }

  // ==========================================================
  // Render
  // ==========================================================

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* ====================================================
          Table Information
      ==================================================== */}

      <div className="flex items-center justify-between gap-3 border-b border-white/6 px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-300">
            Recommendations
          </span>

          <span className="rounded-md bg-white/6 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
            {routes.length.toLocaleString()}
          </span>
        </div>

        <span className="text-xs text-zinc-600">
          Select a route to view details
        </span>
      </div>

      {/* ====================================================
          Scrollable Table
      ==================================================== */}

      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full min-w-242.5 border-separate border-spacing-0 text-left">
          <thead className="sticky top-0 z-10 bg-[#111217]">
            <tr className="border-b border-white/10">
              <SortableHeader
                label="Route"
                column="route"
                activeColumn={sortKey}
                direction={direction}
                onSort={handleSort}
              />

              <SortableHeader
                label="Aircraft"
                column="aircraft"
                activeColumn={sortKey}
                direction={direction}
                onSort={handleSort}
              />

              <th
                scope="col"
                className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500"
              >
                Airline / Flight
              </th>

              <SortableHeader
                label="Duration"
                column="duration"
                activeColumn={sortKey}
                direction={direction}
                onSort={handleSort}
              />

              <th
                scope="col"
                className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500"
              >
                Suitability
              </th>

              <SortableHeader
                label="Flyability"
                column="flyability"
                activeColumn={sortKey}
                direction={direction}
                align="right"
                onSort={handleSort}
              />

              <SortableHeader
                label="Score"
                column="score"
                activeColumn={sortKey}
                direction={direction}
                align="right"
                onSort={handleSort}
              />
            </tr>
          </thead>

          <tbody>
            {sortedRoutes.map((item) => (
              <RouteTableRow
                key={routeKey(item)}
                item={item}
                selected={routeKey(item) === selectedKey}
                onSelect={() => onSelect(item)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* ====================================================
          Table Footer
      ==================================================== */}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/6 bg-[#111217] px-5 py-3">
        <p className="text-xs text-zinc-500">
          Showing{" "}
          <span className="font-medium text-zinc-300">
            {sortedRoutes.length.toLocaleString()}
          </span>{" "}
          routes
        </p>

        <div className="flex items-center gap-3">
          <span className="text-xs text-zinc-600">Sorted by {sortKey}</span>

          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setSortKey("score");
              setDirection("desc");
            }}
            className="h-7 px-2 text-xs text-zinc-400 hover:bg-white/5 hover:text-white"
          >
            Reset sorting
          </Button>
        </div>
      </div>
    </div>
  );
}
