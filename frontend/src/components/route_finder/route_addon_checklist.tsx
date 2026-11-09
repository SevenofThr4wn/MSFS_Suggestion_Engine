"use client";

import {
  CheckCircle2,
  CircleHelp,
  XCircle,
  Plane,
  MapPin,
  Paintbrush,
  Truck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

import type {
  AddonCompatibilityCategory,
  AddonCompatibilityCheck,
  AddonCompatibilityStatus,
  RouteAddonCompatibility,
} from "@/lib/types/validation";

interface RouteAddonChecklistProps {
  compatibility?: RouteAddonCompatibility | null;
  departureIcao: string;
  arrivalIcao: string;
  aircraftName: string;
}

const STATUS_CONFIG = {
  available: {
    label: "Available",
    icon: CheckCircle2,
    className: "border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
  },
  unavailable: {
    label: "Unavailable",
    icon: XCircle,
    className: "border-red-500/20 bg-red-500/10 text-red-400",
  },
  unknown: {
    label: "Unknown",
    icon: CircleHelp,
    className: "border-white/10 bg-white/5 text-zinc-400",
  },
} as const;

const CATEGORY_ICON = {
  aircraft: Plane,
  departure_scenery: MapPin,
  arrival_scenery: MapPin,
  livery: Paintbrush,
  gsx_departure: Truck,
  gsx_arrival: Truck,
};

function defaultChecks(
  aircraftName: string,
  departureIcao: string,
  arrivalIcao: string,
): AddonCompatibilityCheck[] {
  return [
    {
      category: "aircraft",
      label: "Aircraft",
      description: aircraftName,
      status: "unknown",
    },
    {
      category: "departure_scenery",
      label: "Departure scenery",
      description: departureIcao,
      status: "unknown",
    },
    {
      category: "arrival_scenery",
      label: "Arrival scenery",
      description: arrivalIcao,
      status: "unknown",
    },
    {
      category: "livery",
      label: "Aircraft livery",
      status: "unknown",
    },
    {
      category: "gsx_departure",
      label: "Departure GSX profile",
      description: departureIcao,
      status: "unknown",
    },
    {
      category: "gsx_arrival",
      label: "Arrival GSX profile",
      description: arrivalIcao,
      status: "unknown",
    },
  ];
}

function statusBadge(status: AddonCompatibilityStatus) {
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      className={[
        "gap-1 rounded-md px-2 py-1",
        "text-[10px] font-medium",
        config.className,
      ].join(" ")}
    >
      <Icon className="size-3" />
      {config.label}
    </Badge>
  );
}

function ChecklistRow({ item }: { item: AddonCompatibilityCheck }) {
  const Icon = CATEGORY_ICON[item.category];

  return (
    <div className="flex items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/4">
          <Icon className="size-4 text-zinc-500" />
        </div>

        <div className="min-w-0">
          <p className="text-xs font-medium text-zinc-200">{item.label}</p>

          {(item.addonName || item.description) && (
            <p className="mt-1 truncate text-[11px] text-zinc-500">
              {item.addonName ?? item.description}
            </p>
          )}
        </div>
      </div>

      <div className="shrink-0">{statusBadge(item.status)}</div>
    </div>
  );
}

export default function RouteAddonChecklist({
  compatibility,
  departureIcao,
  arrivalIcao,
  aircraftName,
}: RouteAddonChecklistProps) {
  const defaults = defaultChecks(aircraftName, departureIcao, arrivalIcao);

  const checks = defaults.map((fallback) => {
    const actual = compatibility?.checks.find(
      (item) => item.category === fallback.category,
    );

    return actual ?? fallback;
  });

  const available = checks.filter((item) => item.status === "available").length;

  const unavailable = checks.filter(
    (item) => item.status === "unavailable",
  ).length;

  const unknown = checks.filter((item) => item.status === "unknown").length;

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-500">
          Add-on compatibility
        </h3>

        <span className="text-[11px] text-zinc-500">
          {available}/{checks.length} available
        </span>
      </div>

      <div className="rounded-xl border border-white/[0.07] bg-white/2.5 px-3">
        {checks.map((item, index) => (
          <div key={item.category}>
            {index > 0 && <Separator className="bg-white/6" />}

            <ChecklistRow item={item} />
          </div>
        ))}
      </div>

      {(unavailable > 0 || unknown > 0) && (
        <p className="mt-3 text-[11px] leading-5 text-zinc-500">
          {unavailable > 0 && `${unavailable} add-on checks are unavailable. `}
          {unknown > 0 && `${unknown} checks require inventory verification.`}
        </p>
      )}

      {compatibility?.verifiedAt && (
        <p className="mt-2 text-[10px] text-zinc-600">
          Inventory checked: {compatibility.verifiedAt}
        </p>
      )}
    </section>
  );
}
