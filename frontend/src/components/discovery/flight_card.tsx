"use client";

import { ReactNode, useId, useState } from "react";

import {
  Activity,
  ChevronDown,
  MapPin,
  Plane,
  Route as RouteIcon,
  Star,
} from "lucide-react";

import { cn, finite, formatDuration, statusLabel } from "@/lib/utils";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

import { ScoreRing } from "@/components/ui/score_ring";
import { RecommendationAnalysis } from "./recommendation_analysis";
import { FlightPhoto } from "@/components/flights/flight_photo";
import { FlightFeedbackForm } from "@/components/feedback/flight_feedback_form";
import { AirportLocation } from "@/lib/types/airport";
import { Recommendation } from "@/lib/types/recommendation";

interface FlightCardProps {
  item: Recommendation;
  index: number;
  departureLocation?: AirportLocation | null;
  aircraftPhotographyEnabled?: boolean;
}

interface FlightDetailProps {
  icon: ReactNode;
  children: ReactNode;
}

function FlightDetail({ icon, children }: FlightDetailProps) {
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
      <span className="shrink-0 text-primary/80">{icon}</span>

      <span className="min-w-0">{children}</span>
    </span>
  );
}

export function FlightCard({
  item,
  index,
  departureLocation,
  aircraftPhotographyEnabled = false,
}: FlightCardProps) {
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  const reactId = useId();

  const analysisId = `${reactId}-analysis`;
  const feedbackId = `${reactId}-feedback`;

  const route = item.route;
  const gate = item.departure_gate;

  const gateName = gate?.gate?.trim();

  const hasValidGate =
    !!gateName &&
    !["unknown", "n/a", "none", "null", "unavailable"].includes(
      gateName.toLowerCase(),
    );

  const isSuitable = route.suitability === "preliminary_pass";

  const isRealWorld = route.is_real_world_route === true;

  const flightNumber = String(index + 1).padStart(2, "0");

  const distance = finite(route.distance_nm).toLocaleString(undefined, {
    maximumFractionDigits: 0,
  });

  const finalScore = finite(item.final_score).toFixed(1);

  return (
    <Card
      className={cn(
        "flight-card overflow-hidden",
        "border-border bg-card text-card-foreground",
        "transition-colors duration-200",
        "hover:border-primary/30",
      )}
    >
      {/* Flight header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-[10px] font-bold tracking-[0.15em] text-muted-foreground">
          FLIGHT OPTION {flightNumber}
        </span>

        <div className="flex flex-wrap items-center gap-2">
          {isRealWorld && (
            <Badge
              variant="outline"
              className="border-primary/30 bg-primary/10 text-primary"
            >
              Real-world route
            </Badge>
          )}

          <Badge
            variant="outline"
            className={cn(
              "gap-1.5 border text-[10px] font-semibold",
              isSuitable
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                : "border-amber-500/25 bg-amber-500/10 text-amber-300",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "size-1.5 rounded-full",
                isSuitable ? "bg-emerald-400" : "bg-amber-400",
              )}
            />

            {statusLabel(route.suitability)}
          </Badge>
        </div>
      </div>

      {aircraftPhotographyEnabled && (
        <FlightPhoto
          departureIcao={route.departure_icao}
          arrivalIcao={route.arrival_icao}
          arrivalName={route.arrival_name ?? route.arrival_icao}
          aircraftCode={route.aircraft_icao_code}
          airline={isRealWorld ? route.airline_name : null}
          registration={route.registration}
          registrationVerified={route.registration_verified === true}
        />
      )}

      {/* Route overview */}
      <div className="flight-main">
        <div className="flight-route">
          {/* Departure */}
          <div>
            <strong className="text-foreground">{route.departure_icao}</strong>

            <span title={route.departure_name ?? "Departure"}>
              {route.departure_name || "Departure"}
            </span>

            {departureLocation && (
              <span
                className="airport-location"
                title={departureLocation.display_name}
              >
                {departureLocation.display_name}
              </span>
            )}
          </div>

          {/* Flight path */}
          <div className="path">
            <Plane size={18} strokeWidth={1.7} />
            <i aria-hidden="true" />
          </div>

          {/* Arrival */}
          <div>
            <strong className="text-foreground">{route.arrival_icao}</strong>

            <span title={route.arrival_name ?? "Arrival"}>
              {route.arrival_name || "Arrival"}
            </span>

            {item.arrival_location && (
              <span
                className="airport-location"
                title={item.arrival_location.display_name}
              >
                {item.arrival_location.display_name}
              </span>
            )}
          </div>
        </div>

        <div className="replayability-score">
          <ScoreRing score={item.flyability_score} label="REPLAY SCORE" />

          <small>
            {route.flyability_status === "personalized"
              ? "Personalised"
              : "Estimated enjoyment"}
          </small>
        </div>
      </div>

      {/* Aircraft and flight information */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 border-y border-border py-3">
        <FlightDetail icon={<Plane size={14} />}>
          {route.aircraft_name}
        </FlightDetail>

        <FlightDetail icon={<RouteIcon size={14} />}>
          {distance} NM
        </FlightDetail>

        <FlightDetail icon={<Activity size={14} />}>
          {formatDuration(route.estimated_duration_min)}
        </FlightDetail>

        {hasValidGate && (
          <FlightDetail icon={<MapPin size={14} />}>
            Gate {gateName} · candidate
          </FlightDetail>
        )}
      </div>

      {/* Airline information */}
      {route.airline_name && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge
            variant="secondary"
            className="bg-secondary text-secondary-foreground"
          >
            {route.airline_name}
          </Badge>

          {!isRealWorld && (
            <span className="text-[11px] text-muted-foreground">
              Airline association is not route verification
            </span>
          )}
        </div>
      )}

      {/* Card actions */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold tracking-tight text-foreground">
            {finalScore}
          </span>

          <span className="text-xs text-muted-foreground">Final score</span>
        </div>

        <div className="flex flex-wrap items-center gap-1">
          <Button
            type="button"
            variant={feedbackOpen ? "secondary" : "ghost"}
            size="sm"
            className="gap-2 text-xs"
            onClick={() => setFeedbackOpen((previous) => !previous)}
            aria-expanded={feedbackOpen}
            aria-controls={feedbackId}
          >
            <Star size={15} />

            {feedbackOpen ? "Hide feedback" : "Rate flight"}
          </Button>

          <Button
            type="button"
            variant={analysisOpen ? "secondary" : "ghost"}
            size="sm"
            className="gap-2 text-xs"
            onClick={() => setAnalysisOpen((previous) => !previous)}
            aria-expanded={analysisOpen}
            aria-controls={analysisId}
          >
            {analysisOpen ? "Hide analysis" : "View analysis"}

            <ChevronDown
              size={15}
              className={cn(
                "transition-transform duration-200",
                analysisOpen && "rotate-180",
              )}
            />
          </Button>
        </div>
      </div>

      {/* Expanded recommendation analysis */}
      {analysisOpen && (
        <div id={analysisId} className="mt-4">
          <Separator className="mb-4" />

          <RecommendationAnalysis item={item} />
        </div>
      )}

      {/* Flight feedback form */}
      {feedbackOpen && (
        <div id={feedbackId} className="mt-4">
          <Separator className="mb-4" />

          <FlightFeedbackForm
            departure={route.departure_icao}
            arrival={route.arrival_icao}
            aircraftId={route.aircraft_id}
          />
        </div>
      )}
    </Card>
  );
}
