"use client";

import { ArrowRight, Plane, Star } from "lucide-react";
import type { ScoredRecommendation } from "@/lib/types/recommendation";
import { formatDistance, formatDuration } from "@/lib/route_finder";
import RouteStatusBadge from "./route_status_badge";

interface RouteTableRowProps {
  item: ScoredRecommendation;
  selected: boolean;
  onSelect: () => void;
}

function formatScore(value: number): string {
  return Number.isFinite(value) ? value.toFixed(1) : "—";
}

export default function RouteTableRow({
  item,
  selected,
  onSelect,
}: RouteTableRowProps) {
  const route = item.route;

  return (
    <tr
      onClick={onSelect}
      aria-selected={selected}
      className={[
        "group cursor-pointer border-b",
        "border-white/6 transition-colors",
        selected ? "bg-amber-400/8" : "hover:bg-white/[0.035]",
      ].join(" ")}
    >
      {/* Route */}

      <td
        className={[
          "border-l-2 px-5 py-4",
          selected ? "border-amber-400" : "border-transparent",
        ].join(" ")}
      >
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onSelect();
          }}
          aria-pressed={selected}
          aria-label={
            `Select flight ${route.departure_icao} ` +
            `to ${route.arrival_icao} on ${route.aircraft_name}`
          }
          className="block w-full rounded-sm text-left outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
        >
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-semibold text-zinc-100">
              {route.departure_icao}
            </span>

            <ArrowRight className="size-3.5 text-amber-400/70" />

            <span className="font-mono text-sm font-semibold text-zinc-100">
              {route.arrival_icao}
            </span>
          </div>

          <p
            title={`${route.departure_name} → ${route.arrival_name}`}
            className="mt-1 max-w-60 truncate text-xs text-zinc-500"
          >
            {route.departure_name}
            {" → "}
            {route.arrival_name}
          </p>
        </button>
      </td>

      {/* Aircraft */}

      <td className="px-4 py-4">
        <div className="flex items-center gap-2">
          <Plane className="size-3.5 shrink-0 text-zinc-500" />

          <span
            title={route.aircraft_name}
            className="max-w-48 truncate text-sm font-medium text-zinc-200"
          >
            {route.aircraft_name}
          </span>
        </div>

        <p className="mt-1 pl-5.5 font-mono text-xs text-zinc-500">
          {route.aircraft_icao_code ?? "—"}
        </p>
      </td>

      {/* Airline and flight number */}

      <td className="px-4 py-4">
        <p
          title={route.airline_name ?? undefined}
          className="max-w-40 truncate text-sm text-zinc-300"
        >
          {route.airline_name ?? "Unassigned"}
        </p>

        <p className="mt-1 font-mono text-xs text-zinc-500">
          {route.flight_number ?? "No flight number"}
        </p>
      </td>

      {/* Duration and distance */}

      <td className="px-4 py-4">
        <p className="whitespace-nowrap font-mono text-sm font-medium text-zinc-200">
          {formatDuration(route.estimated_duration_min)}
        </p>

        <p className="mt-1 whitespace-nowrap font-mono text-xs text-zinc-500">
          {formatDistance(route.distance_nm)}
        </p>
      </td>

      {/* Suitability */}

      <td className="px-4 py-4">
        <RouteStatusBadge status={route.suitability} compact />
      </td>

      {/* Flyability */}

      <td className="px-4 py-4 text-right">
        <div className="flex items-center justify-end gap-1.5">
          <Star className="size-3.5 text-zinc-500" />

          <span className="font-mono text-sm text-zinc-300">
            {formatScore(route.flyability_score)}
          </span>
        </div>
      </td>

      {/* Final recommendation score */}

      <td className="px-5 py-4 text-right">
        <span
          className={[
            "font-mono text-sm font-semibold",
            selected ? "text-amber-300" : "text-amber-400",
          ].join(" ")}
        >
          {formatScore(item.final_score)}
        </span>
      </td>
    </tr>
  );
}
