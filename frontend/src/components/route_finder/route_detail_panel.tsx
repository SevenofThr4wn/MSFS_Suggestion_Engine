"use client";

import type { ReactNode } from "react";

import {
  AlertTriangle,
  ArrowRight,
  Clock3,
  Compass,
  MapPin,
  Plane,
  Route,
  ShieldCheck,
  Star,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { ScoredRecommendation } from "@/lib/types/recommendation";
import type { RouteMapCoordinates } from "@/lib/types/route_finder";
import type { RouteAddonCompatibility } from "@/lib/types/validation";
import { formatDistance, formatDuration } from "@/lib/route_finder";
import RouteStatusBadge from "./route_status_badge";
import RouteAddonChecklist from "./route_addon_checklist";
import RoutePreviewMap from "./route_preview_map";

interface RouteDetailPanelProps {
  route: ScoredRecommendation | null;

  coordinates?: RouteMapCoordinates | null;
  compatibility?: RouteAddonCompatibility | null;
}

function formatScore(value: number): string {
  return Number.isFinite(value) ? value.toFixed(1) : "—";
}

function DetailRow({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 py-2.5">
      <div className="flex min-w-0 items-center gap-2 text-zinc-500">
        <span className="shrink-0">{icon}</span>

        <span className="text-xs">{label}</span>
      </div>

      <div className="max-w-[60%] text-right text-xs font-medium text-zinc-200">
        {value}
      </div>
    </div>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
      {children}
    </h3>
  );
}

export default function RouteDetailPanel({
  route: selected,
  coordinates,
  compatibility,
}: RouteDetailPanelProps) {
  if (!selected) {
    return (
      <aside className="flex min-h-125 flex-col items-center justify-center gap-4 border-l border-white/10 bg-[#101116] p-6 text-center">
        <div className="flex size-14 items-center justify-center rounded-2xl border border-white/10 bg-white/4">
          <Compass className="size-6 text-zinc-500" />
        </div>

        <div>
          <p className="text-sm font-medium text-zinc-300">
            No flight selected
          </p>

          <p className="mt-2 max-w-56 text-xs leading-5 text-zinc-500">
            Select a recommendation from the table to explore the flight.
          </p>
        </div>
      </aside>
    );
  }

  const flight = selected.route;

  const reasons =
    selected.reasons.length > 0 ? selected.reasons : flight.reasons;

  const warnings = [
    ...new Set([...flight.warnings, ...(selected.warnings ?? [])]),
  ];

  const hasRealWorldEvidence = flight.is_real_world_route;

  return (
    <aside className="flex h-full min-h-0 flex-col overflow-hidden border-l border-white/10 bg-[#101116]">
      <div className="shrink-0 border-b border-white/10 px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-semibold uppercase tracking-widest text-zinc-500">
            Flight details
          </span>

          <RouteStatusBadge status={flight.suitability} compact />
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <section className="px-5 py-5">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="font-mono text-2xl font-bold tracking-tight text-white">
                {flight.departure_icao}
              </p>
              <p
                title={flight.departure_name}
                className="mt-1 max-w-28 truncate text-xs text-zinc-500"
              >
                {flight.departure_name}
              </p>
            </div>

            <div className="flex flex-1 flex-col items-center justify-center gap-2 pt-2">
              <div className="flex w-full items-center gap-2">
                <div className="h-px flex-1 bg-white/10" />

                <ArrowRight className="size-4 shrink-0 text-amber-400" />

                <div className="h-px flex-1 bg-white/10" />
              </div>

              <span className="whitespace-nowrap font-mono text-[11px] text-zinc-500">
                {formatDuration(flight.estimated_duration_min)}
              </span>
            </div>

            <div className="min-w-0 text-right">
              <p className="font-mono text-2xl font-bold tracking-tight text-white">
                {flight.arrival_icao}
              </p>

              <p
                title={flight.arrival_name}
                className="mt-1 max-w-28 truncate text-xs text-zinc-500"
              >
                {flight.arrival_name}
              </p>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Badge
              variant="outline"
              className="border-white/10 bg-white/4 text-[10px] text-zinc-400"
            >
              {hasRealWorldEvidence
                ? "Real-world route evidence"
                : "Unverified route"}
            </Badge>

            {flight.flight_number && (
              <Badge
                variant="outline"
                className="border-white/10 bg-white/4 font-mono text-[10px] text-zinc-300"
              >
                {flight.flight_number}
              </Badge>
            )}
          </div>
        </section>

        <section className="px-5 pb-5">
          <RoutePreviewMap coordinates={coordinates} height={190} />
        </section>
        <Separator className="bg-white/[0.07]" />
        <section className="px-5 py-5">
          <SectionTitle>Flight information</SectionTitle>

          <div className="divide-y divide-white/6">
            <DetailRow
              icon={<Plane className="size-3.5" />}
              label="Aircraft"
              value={flight.aircraft_name}
            />

            <DetailRow
              icon={<MapPin className="size-3.5" />}
              label="Airline"
              value={flight.airline_name ?? "Not assigned"}
            />

            <DetailRow
              icon={<Route className="size-3.5" />}
              label="Flight number"
              value={flight.flight_number ?? "—"}
            />

            <DetailRow
              icon={<Clock3 className="size-3.5" />}
              label="Duration"
              value={formatDuration(flight.estimated_duration_min)}
            />

            <DetailRow
              icon={<Compass className="size-3.5" />}
              label="Distance"
              value={formatDistance(flight.distance_nm)}
            />
          </div>
        </section>

        <Separator className="bg-white/[0.07]" />

        <section className="px-5 py-5">
          <SectionTitle>Recommendation scoring</SectionTitle>

          <div className="mb-4 flex items-center justify-between rounded-xl border border-amber-400/10 bg-amber-400/5 px-4 py-3">
            <div className="flex items-center gap-2 text-xs text-zinc-300">
              <Star className="size-4 text-amber-400" />
              Final score
            </div>

            <span className="font-mono text-xl font-bold text-amber-400">
              {formatScore(selected.final_score)}
            </span>
          </div>

          <div className="divide-y divide-white/6">
            <DetailRow
              icon={<Star className="size-3.5" />}
              label="Flyability"
              value={formatScore(selected.flyability_score)}
            />

            <DetailRow
              icon={<Compass className="size-3.5" />}
              label="Preference"
              value={formatScore(selected.preference_score)}
            />

            <DetailRow
              icon={<ShieldCheck className="size-3.5" />}
              label="Realism"
              value={
                selected.realism_score === null
                  ? "Not evaluated"
                  : formatScore(selected.realism_score)
              }
            />
          </div>
        </section>

        <Separator className="bg-white/[0.07]" />
        <div className="px-5 py-5">
          <RouteAddonChecklist
            compatibility={compatibility}
            departureIcao={flight.departure_icao}
            arrivalIcao={flight.arrival_icao}
            aircraftName={flight.aircraft_name}
          />
        </div>

        <Separator className="bg-white/[0.07]" />

        <section className="px-5 py-5">
          <SectionTitle>Why this flight?</SectionTitle>

          {reasons.length > 0 ? (
            <div className="space-y-2">
              {reasons.map((reason, index) => (
                <p
                  key={`${index}-${reason}`}
                  className="rounded-lg border border-white/5 bg-white/3 px-3 py-2 text-xs leading-5 text-zinc-400"
                >
                  {reason}
                </p>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-500">
              No additional explanation was provided.
            </p>
          )}
        </section>

        {warnings.length > 0 && (
          <>
            <Separator className="bg-white/[0.07]" />

            <section className="px-5 py-5">
              <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                <AlertTriangle className="size-4 text-amber-400" />
                Warnings
              </h3>

              <div className="space-y-2">
                {warnings.map((warning, index) => (
                  <p
                    key={`${index}-${warning}`}
                    className="text-xs leading-5 text-zinc-500"
                  >
                    {warning}
                  </p>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </aside>
  );
}
