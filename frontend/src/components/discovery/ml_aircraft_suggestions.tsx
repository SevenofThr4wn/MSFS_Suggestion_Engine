"use client";

import { useEffect, useState } from "react";

import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Info,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";

import type { HybridAircraftPrediction, MLReliability } from "@/lib/types/ml";
import type { RouteRecommendation as Route } from "@/lib/types/route";
import { useAircraftPrediction } from "@/lib/hooks/use_aircraft_prediction";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface MLAircraftSuggestionsProps {
  route: Route;
}

function reliabilityLabel(value: MLReliability): string {
  switch (value) {
    case "higher":
      return "Higher";
    case "moderate":
      return "Moderate";
    case "low":
      return "Low";
    default:
      return "Unknown";
  }
}

function reliabilityClasses(value: MLReliability): string {
  switch (value) {
    case "higher":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    case "moderate":
      return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    case "low":
      return "border-orange-500/30 bg-orange-500/10 text-orange-300";
    default:
      return "border-border bg-secondary text-muted-foreground";
  }
}

function ModelScore({
  label,
  score,
  matching = false,
}: {
  label: string;
  score: number;
  matching?: boolean;
}) {
  const percentage = Math.max(0, Math.min(100, score * 100));

  return (
    <div className="min-w-0 space-y-1.5">
      <div className="flex items-start justify-between gap-3 text-xs">
        <span className="min-w-0 wrap-break-word text-foreground">
          {label}
          {matching && (
            <CheckCircle2 className="ml-1.5 inline size-3.5 text-emerald-400" />
          )}
        </span>

        <span className="shrink-0 font-mono text-muted-foreground">
          {percentage.toFixed(1)}%
        </span>
      </div>

      <Progress value={percentage} className="h-1.5" />
    </div>
  );
}

function PredictionResults({ data }: { data: HybridAircraftPrediction }) {
  const variantEligible =
    data.variant_recommendation_eligible ??
    (data.model_agreement === "agree" &&
      ["moderate", "higher"].includes(data.family_reliability) &&
      ["moderate", "higher"].includes(data.variant_reliability));

  return (
    <div className="min-w-0 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Predicted aircraft family
          </p>

          <p className="text-base font-semibold text-foreground">
            {data.predicted_family_name ?? "Unknown family"}
          </p>
        </div>

        <Badge
          variant="outline"
          className={reliabilityClasses(data.reliability)}
        >
          {reliabilityLabel(data.reliability)} reliability
        </Badge>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border bg-secondary/20 p-3">
          <p className="text-[10px] text-muted-foreground">Model agreement</p>

          <p className="mt-1 text-sm font-medium capitalize">
            {data.model_agreement}
          </p>
        </div>

        <div className="rounded-lg border border-border bg-secondary/20 p-3">
          <p className="text-[10px] text-muted-foreground">
            Family reliability
          </p>

          <p className="mt-1 text-sm font-medium">
            {reliabilityLabel(data.family_reliability)}
          </p>
        </div>

        <div className="rounded-lg border border-border bg-secondary/20 p-3">
          <p className="text-[10px] text-muted-foreground">
            Variant reliability
          </p>

          <p className="mt-1 text-sm font-medium">
            {reliabilityLabel(data.variant_reliability)}
          </p>
        </div>
      </div>

      {data.predicted_aircraft_icao && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-3">
          <div>
            <p className="text-[10px] text-muted-foreground">
              Leading aircraft variant
            </p>

            <p className="mt-1 font-semibold">{data.predicted_aircraft_icao}</p>
          </div>

          <Badge variant="outline">
            {variantEligible
              ? "Eligible suggestion"
              : "Low-confidence suggestion"}
          </Badge>
        </div>
      )}

      {data.family_candidates.length > 0 && (
        <section className="space-y-3">
          <h4 className="text-xs font-semibold">Aircraft families</h4>

          {data.family_candidates.slice(0, 3).map((candidate) => (
            <ModelScore
              key={candidate.family_id}
              label={candidate.family_name}
              score={candidate.model_score}
              matching={candidate.family_id === data.predicted_family_id}
            />
          ))}
        </section>
      )}

      {data.suggested_variants.length > 0 && (
        <section className="space-y-3">
          <h4 className="text-xs font-semibold">Aircraft variants</h4>

          {data.suggested_variants.map((candidate) => (
            <ModelScore
              key={candidate.aircraft_icao}
              label={[candidate.aircraft_icao, candidate.family_name]
                .filter(Boolean)
                .join(" · ")}
              score={candidate.model_score}
              matching={candidate.matches_predicted_family}
            />
          ))}
        </section>
      )}

      {data.warnings.length > 0 && (
        <div className="space-y-2">
          {data.warnings.map((warning, index) => (
            <div
              key={`${warning}-${index}`}
              className="flex items-start gap-2 text-xs text-amber-300"
            >
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-start gap-2 border-t border-border pt-3 text-[11px] leading-relaxed text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        <p>
          {data.disclaimer} Scores are uncalibrated model outputs, not verified
          flight probabilities.
        </p>
      </div>
    </div>
  );
}

export function MLAircraftSuggestions({ route }: MLAircraftSuggestionsProps) {
  const [open, setOpen] = useState(false);
  const [selectedAirlineIcao, setSelectedAirlineIcao] = useState("");
  const [requestedKey, setRequestedKey] = useState<string | null>(null);

  const { prediction, loading, error, predict, cancel } =
    useAircraftPrediction();

  // Airline from route metadata, if available.
  const routeAirlineIcao = (route.airline_icao ?? "").trim().toUpperCase();

  // Otherwise allow an airline to be entered manually.
  const airlineIcao =
    routeAirlineIcao || selectedAirlineIcao.trim().toUpperCase();

  const departureIcao = route.departure_icao;
  const arrivalIcao = route.arrival_icao;
  const distanceNm = route.distance_nm;

  const hasAssignedAirline = /^[A-Z]{3}$/.test(routeAirlineIcao);

  const validAirlineIcao = /^[A-Z]{3}$/.test(airlineIcao);

  const validDistance =
    typeof distanceNm === "number" &&
    Number.isFinite(distanceNm) &&
    distanceNm > 0;

  const validAirports =
    /^[A-Z]{4}$/.test(departureIcao) && /^[A-Z]{4}$/.test(arrivalIcao);

  const canPredict = validAirlineIcao && validDistance && validAirports;

  // Identify the precise inputs associated with a prediction.
  const currentKey = [airlineIcao, departureIcao, arrivalIcao, distanceNm].join(
    ":",
  );

  // Prevent old prediction results from appearing when
  // the airline or route changes.
  const hasCurrentRequest = requestedKey === currentKey;

  const currentPrediction = hasCurrentRequest ? prediction : null;

  const currentError = hasCurrentRequest ? error : null;

  useEffect(() => {
    return () => cancel();
  }, [cancel]);

  function requestPrediction() {
    if (!canPredict) return;

    setRequestedKey(currentKey);

    void predict({
      airline_icao: airlineIcao,
      departure_icao: departureIcao,
      arrival_icao: arrivalIcao,
      distance_nm: distanceNm,
    });
  }

  function handleAirlineChange(event: React.ChangeEvent<HTMLInputElement>) {
    const value = event.target.value
      .toUpperCase()
      .replace(/[^A-Z]/g, "")
      .slice(0, 3);

    cancel();
    setRequestedKey(null);
    setSelectedAirlineIcao(value);
  }

  function toggleOpen() {
    if (open) {
      cancel();
      setOpen(false);
      return;
    }

    setOpen(true);

    // Automatically predict only when the route already
    // has a valid airline identifier.
    if (hasAssignedAirline && canPredict) {
      requestPrediction();
    }
  }

  return (
    <section className="min-w-0 overflow-hidden rounded-xl border border-border bg-card">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex min-w-0 items-center gap-3">
          <BrainCircuit className="size-5 shrink-0 text-primary" />

          <div>
            <h3 className="text-sm font-semibold">ML Aircraft Suggestions</h3>

            <p className="mt-1 text-xs text-muted-foreground">
              Historical airline and aircraft predictions
            </p>
          </div>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={toggleOpen}
          aria-expanded={open}
        >
          {open ? "Hide suggestions" : "View ML suggestions"}

          <ChevronDown
            className={cn("size-4 transition-transform", open && "rotate-180")}
          />
        </Button>
      </div>

      {open && (
        <div className="min-w-0 space-y-4 border-t border-border p-4">
          {/* Airline selection for geographic discovery */}
          {!hasAssignedAirline && (
            <div className="space-y-3 rounded-lg border border-border bg-secondary/20 p-4">
              <div className="space-y-1">
                <h4 className="text-xs font-semibold">Select an airline</h4>

                <p className="text-xs leading-relaxed text-muted-foreground">
                  No airline is assigned to this route. Enter an airline ICAO
                  code to explore which aircraft the ML models associate with
                  this airline and route.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Input
                  value={selectedAirlineIcao}
                  onChange={handleAirlineChange}
                  placeholder="e.g. UAE"
                  maxLength={3}
                  aria-label="Airline ICAO code"
                  autoComplete="off"
                  spellCheck={false}
                  className="w-36 font-mono uppercase"
                />

                <Button
                  type="button"
                  size="sm"
                  disabled={!canPredict || loading}
                  onClick={requestPrediction}
                  className="gap-2"
                >
                  {loading && hasCurrentRequest ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <BrainCircuit className="size-4" />
                  )}
                  Predict aircraft
                </Button>
              </div>

              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Example: UAE for Emirates. Manual airline selection is
                hypothetical and does not verify that the airline operates this
                route.
              </p>
            </div>
          )}

          {/* Input validation */}
          {!validAirports ? (
            <div className="flex items-start gap-2 text-xs text-amber-300">
              <AlertTriangle className="size-4 shrink-0" />

              <p>
                Aircraft predictions require valid departure and arrival ICAO
                airport codes.
              </p>
            </div>
          ) : !validDistance ? (
            <div className="flex items-start gap-2 text-xs text-amber-300">
              <AlertTriangle className="size-4 shrink-0" />

              <p>
                Aircraft predictions are unavailable because the route distance
                is missing or invalid.
              </p>
            </div>
          ) : !validAirlineIcao ? (
            <div className="flex items-start gap-2 text-xs text-muted-foreground">
              <Info className="size-4 shrink-0 text-primary" />

              <p>
                Enter a three-letter airline ICAO code to generate aircraft
                predictions.
              </p>
            </div>
          ) : loading && hasCurrentRequest ? (
            /* Loading */
            <div
              role="status"
              className="flex items-center gap-2 py-6 text-sm text-muted-foreground"
            >
              <LoaderCircle className="size-4 animate-spin" />
              Evaluating aircraft predictions...
            </div>
          ) : currentError ? (
            /* Error */
            <div className="space-y-3">
              <div className="flex items-start gap-2 text-xs text-destructive">
                <AlertTriangle className="size-4 shrink-0" />

                <p>{currentError}</p>
              </div>

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={requestPrediction}
                className="gap-2"
              >
                <RefreshCw className="size-3.5" />
                Retry prediction
              </Button>
            </div>
          ) : currentPrediction ? (
            /* Successful prediction */
            <div className="space-y-4">
              {!hasAssignedAirline && (
                <div className="flex items-start gap-2 rounded-lg border border-border bg-secondary/20 p-3 text-xs text-muted-foreground">
                  <Info className="mt-0.5 size-4 shrink-0 text-primary" />

                  <p>
                    Hypothetical prediction for airline{" "}
                    <span className="font-mono font-semibold text-foreground">
                      {airlineIcao}
                    </span>
                    . This does not establish that the airline operates this
                    flight.
                  </p>
                </div>
              )}

              <PredictionResults data={currentPrediction} />
            </div>
          ) : (
            /* Ready for prediction */
            <div className="flex items-start gap-2 text-xs text-muted-foreground">
              <Info className="size-4 shrink-0 text-primary" />

              <p>
                {hasAssignedAirline
                  ? "Select View ML suggestions to request an aircraft prediction."
                  : "Select Predict aircraft to evaluate the selected airline and route."}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
