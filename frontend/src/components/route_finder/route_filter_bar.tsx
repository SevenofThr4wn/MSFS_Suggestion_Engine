"use client";

import {
  Filter,
  RotateCcw,
  Search,
  Settings2,
  SlidersHorizontal,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import type { RouteFinderFilters } from "@/lib/types/route_finder";
import type { AircraftCategory } from "@/lib/types/aircraft";
import type { AirportMode } from "@/lib/types/airport";
import RouteFilterPopover from "./route_filter_popover";

interface RouteFilterBarProps {
  filters: RouteFinderFilters;
  loading: boolean;

  onChange: (patch: Partial<RouteFinderFilters>) => void;

  onReset: () => void;
  onGenerate: () => void;
}

const AIRCRAFT_CATEGORIES: {
  value: AircraftCategory | "";
  label: string;
}[] = [
  { value: "", label: "All aircraft" },
  { value: "narrow_body", label: "Narrow body" },
  { value: "wide_body", label: "Wide body" },
  { value: "regional_jet", label: "Regional jet" },
  { value: "turboprop", label: "Turboprop" },
];

const AIRPORT_MODES: {
  value: AirportMode;
  label: string;
  description: string;
}[] = [
  {
    value: "all",
    label: "All airports",
    description: "No geographic catalog restrictions",
  },
  {
    value: "major",
    label: "Major airports",
    description: "Focus on larger airports",
  },
  {
    value: "main_hubs",
    label: "Main hubs",
    description: "Curated international hub network",
  },
  {
    value: "commercial",
    label: "Commercial",
    description: "Airports with commercial operations",
  },
];

const inputClasses = [
  "h-9 border-white/10 bg-[#101116]",
  "text-sm text-zinc-200",
  "placeholder:text-zinc-600",
  "focus-visible:border-amber-400/50",
  "focus-visible:ring-amber-400/20",
].join(" ");

export default function RouteFilterBar({
  filters,
  loading,
  onChange,
  onReset,
  onGenerate,
}: RouteFilterBarProps) {
  const aircraftActive = filters.aircraftCategory !== "";

  const airportActive = filters.airportMode !== "all";

  const routeActive =
    filters.departureCode.trim() !== "" || filters.arrivalCode.trim() !== "";

  const durationActive =
    filters.minDurationHours !== 1 || filters.maxDurationHours !== 12;

  const preferenceCount = [
    filters.ownedOnly,
    filters.preferAddonScenery,
    filters.includeIndeterminate,
    filters.requireRealWorldRoute,
  ].filter(Boolean).length;

  const invalidDuration =
    !Number.isFinite(filters.minDurationHours) ||
    !Number.isFinite(filters.maxDurationHours) ||
    filters.minDurationHours <= 0 ||
    filters.maxDurationHours < filters.minDurationHours;

  const invalidAirport =
    !/^[A-Z]{4}$/.test(filters.departureCode.trim()) ||
    (filters.arrivalCode.trim() !== "" &&
      !/^[A-Z]{4}$/.test(filters.arrivalCode.trim()));

  function handleAirportChange(
    field: "departureCode" | "arrivalCode",
    value: string,
  ) {
    onChange({
      [field]: value
        .replace(/[^a-zA-Z]/g, "")
        .toUpperCase()
        .slice(0, 4),
    });
  }

  function handleDurationChange(
    field: "minDurationHours" | "maxDurationHours",
    value: string,
  ) {
    onChange({
      [field]: value === "" ? NaN : Number(value),
    });
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (invalidDuration || invalidAirport || loading) {
      return;
    }

    onGenerate();
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-b border-white/10 bg-[#0e0f13] px-6 py-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <div className="mr-2 flex items-center gap-2 text-xs font-medium text-zinc-500">
          <Filter className="size-4" />
          Filters
        </div>

        <RouteFilterPopover
          label="From / To"
          description="Choose your departure and optional destination airport."
          active={routeActive}
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="rf-departure">Departure</Label>

              <Input
                id="rf-departure"
                placeholder="YBBN"
                value={filters.departureCode}
                onChange={(event) =>
                  handleAirportChange("departureCode", event.target.value)
                }
                className={inputClasses}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="rf-arrival">Arrival</Label>

              <Input
                id="rf-arrival"
                placeholder="Anywhere"
                value={filters.arrivalCode}
                onChange={(event) =>
                  handleAirportChange("arrivalCode", event.target.value)
                }
                className={inputClasses}
              />
            </div>
          </div>

          <p className="text-xs text-zinc-500">
            Use ICAO airport codes. Leave arrival blank to discover multiple
            destinations.
          </p>
        </RouteFilterPopover>
        <RouteFilterPopover
          label="Aircraft"
          description="Filter recommendations by aircraft category."
          active={aircraftActive}
        >
          <div className="space-y-1">
            {AIRCRAFT_CATEGORIES.map((category) => {
              const selected = filters.aircraftCategory === category.value;

              return (
                <button
                  key={category.value}
                  type="button"
                  onClick={() =>
                    onChange({
                      aircraftCategory: category.value,
                    })
                  }
                  className={[
                    "flex w-full items-center justify-between",
                    "rounded-lg px-3 py-2.5 text-left text-sm",
                    "transition-colors",
                    selected
                      ? "bg-amber-400/10 text-amber-300"
                      : "text-zinc-400 hover:bg-white/5",
                  ].join(" ")}
                >
                  {category.label}

                  {selected && (
                    <span className="size-2 rounded-full bg-amber-400" />
                  )}
                </button>
              );
            })}
          </div>

          <Separator className="bg-white/10" />

          <FilterSwitch
            id="rf-owned"
            label="Owned aircraft only"
            description="Use aircraft marked as owned in FlightEngine."
            checked={filters.ownedOnly}
            onChange={(ownedOnly) => onChange({ ownedOnly })}
          />
        </RouteFilterPopover>
        <RouteFilterPopover
          label="Airports"
          description="Select which airports are considered during discovery."
          active={airportActive}
        >
          <div className="space-y-1">
            {AIRPORT_MODES.map((mode) => {
              const selected = filters.airportMode === mode.value;

              return (
                <button
                  key={mode.value}
                  type="button"
                  onClick={() =>
                    onChange({
                      airportMode: mode.value,
                    })
                  }
                  className={[
                    "flex w-full items-center justify-between",
                    "rounded-lg px-3 py-2.5 text-left",
                    "transition-colors",
                    selected ? "bg-amber-400/10" : "hover:bg-white/5",
                  ].join(" ")}
                >
                  <div>
                    <p
                      className={
                        selected
                          ? "text-sm text-amber-300"
                          : "text-sm text-zinc-300"
                      }
                    >
                      {mode.label}
                    </p>

                    <p className="mt-1 text-xs text-zinc-500">
                      {mode.description}
                    </p>
                  </div>

                  {selected && (
                    <span className="ml-3 size-2 shrink-0 rounded-full bg-amber-400" />
                  )}
                </button>
              );
            })}
          </div>
        </RouteFilterPopover>
        <RouteFilterPopover
          label="Duration"
          description="Set your preferred flight duration range."
          active={durationActive}
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="rf-min-duration">Minimum hours</Label>

              <Input
                id="rf-min-duration"
                type="number"
                min={0.5}
                max={24}
                step={0.5}
                value={
                  Number.isNaN(filters.minDurationHours)
                    ? ""
                    : filters.minDurationHours
                }
                onChange={(event) =>
                  handleDurationChange("minDurationHours", event.target.value)
                }
                className={inputClasses}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="rf-max-duration">Maximum hours</Label>

              <Input
                id="rf-max-duration"
                type="number"
                min={0.5}
                max={24}
                step={0.5}
                value={
                  Number.isNaN(filters.maxDurationHours)
                    ? ""
                    : filters.maxDurationHours
                }
                onChange={(event) =>
                  handleDurationChange("maxDurationHours", event.target.value)
                }
                className={inputClasses}
              />
            </div>
          </div>

          <div className="rounded-lg bg-white/4 px-3 py-2 text-center text-sm text-zinc-300">
            {Number.isFinite(filters.minDurationHours)
              ? filters.minDurationHours
              : "—"}
            {" – "}
            {Number.isFinite(filters.maxDurationHours)
              ? filters.maxDurationHours
              : "—"}
            {" hours"}
          </div>

          {invalidDuration && (
            <p className="text-xs text-red-400">
              Enter a valid range with minimum no greater than maximum.
            </p>
          )}
        </RouteFilterPopover>
        <RouteFilterPopover
          label="Preferences"
          description="Control scenery preferences and recommendation eligibility."
          activeCount={preferenceCount}
        >
          <div className="space-y-4">
            <FilterSwitch
              id="rf-scenery"
              label="Prefer add-on scenery"
              description="Prioritize destinations with installed scenery."
              checked={filters.preferAddonScenery}
              onChange={(preferAddonScenery) =>
                onChange({ preferAddonScenery })
              }
            />

            <Separator className="bg-white/10" />

            <FilterSwitch
              id="rf-indeterminate"
              label="Include uncertain routes"
              description="Allow recommendations with incomplete suitability data."
              checked={filters.includeIndeterminate}
              onChange={(includeIndeterminate) =>
                onChange({ includeIndeterminate })
              }
            />

            <Separator className="bg-white/10" />

            <FilterSwitch
              id="rf-real-world"
              label="Verified routes only"
              description="Require real-world route evidence."
              checked={filters.requireRealWorldRoute}
              onChange={(requireRealWorldRoute) =>
                onChange({ requireRealWorldRoute })
              }
            />
          </div>
        </RouteFilterPopover>
        <RouteFilterPopover
          label="Results"
          description="Set the maximum number of recommendations."
        >
          <div className="space-y-2">
            <Label htmlFor="rf-limit">Maximum results</Label>

            <Input
              id="rf-limit"
              type="number"
              min={1}
              max={100}
              step={1}
              value={filters.limit}
              onChange={(event) =>
                onChange({
                  limit:
                    event.target.value === ""
                      ? NaN
                      : Number(event.target.value),
                })
              }
              className={inputClasses}
            />
          </div>
        </RouteFilterPopover>
        <div className="hidden flex-1 lg:block" />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          title="Reset filters"
          onClick={onReset}
          className="size-9 text-zinc-500 hover:bg-white/5 hover:text-white"
        >
          <RotateCcw className="size-4" />
        </Button>
        <Button
          type="submit"
          disabled={
            loading ||
            invalidAirport ||
            invalidDuration ||
            !Number.isInteger(filters.limit) ||
            filters.limit < 1 ||
            filters.limit > 100
          }
          className="h-9 gap-2 rounded-full bg-amber-400 px-5 font-semibold text-zinc-950 hover:bg-amber-300"
        >
          <Search className="size-4" />

          {loading ? "Searching..." : "Find routes"}
        </Button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
        <SlidersHorizontal className="size-3.5" />

        <span>
          {filters.departureCode || "Any departure"}
          {" → "}
          {filters.arrivalCode || "Anywhere"}
        </span>

        <span className="text-zinc-700">•</span>

        <span>
          {filters.aircraftCategory
            ? AIRCRAFT_CATEGORIES.find(
                (item) => item.value === filters.aircraftCategory,
              )?.label
            : "All aircraft"}
        </span>

        <span className="text-zinc-700">•</span>

        <span>
          {filters.minDurationHours}–{filters.maxDurationHours}h
        </span>

        <span className="text-zinc-700">•</span>

        <span>Up to {filters.limit} results</span>

        <Settings2 className="ml-auto size-3.5 text-zinc-700" />
      </div>
    </form>
  );
}

interface FilterSwitchProps {
  id: string;
  label: string;
  description?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}

function FilterSwitch({
  id,
  label,
  description,
  checked,
  onChange,
}: FilterSwitchProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="min-w-0 space-y-1">
        <Label
          htmlFor={id}
          className="cursor-pointer text-sm font-medium text-zinc-200"
        >
          {label}
        </Label>

        {description && (
          <p className="text-xs leading-5 text-zinc-500">{description}</p>
        )}
      </div>

      <Switch
        id={id}
        checked={checked}
        onCheckedChange={onChange}
        className="shrink-0"
      />
    </div>
  );
}
