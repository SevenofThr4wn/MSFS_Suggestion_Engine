import {
  CircleAlert,
  Gauge,
  Info,
  Radar,
  ShieldCheck,
  Terminal,
  Waypoints,
  MapPin,
} from "lucide-react";

import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

import { FlightCard } from "./flight_card";
import { DecisionTracePanel } from "./decision_trace_panel";
import { RecommendationResponse } from "@/lib/types/recommendation";

interface RecommendationResultsProps {
  response: RecommendationResponse | null;
  aircraftPhotographyEnabled?: boolean;
  loading: boolean;
}

interface StatCardProps {
  label: string;
  value: number;
  description: string;
  accent?: boolean;
}

function StatCard({
  label,
  value,
  description,
  accent = false,
}: StatCardProps) {
  return (
    <Card className="min-w-0 gap-0 border-border bg-card py-0">
      <CardContent className="p-4">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>

        <p
          className={
            accent
              ? "mt-2 text-2xl font-bold tracking-tight text-primary"
              : "mt-2 text-2xl font-bold tracking-tight text-foreground"
          }
        >
          {value.toLocaleString()}
        </p>

        <p className="mt-1 text-[11px] text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

interface EmptyResultsProps {
  icon: ReactNode;
  title: string;
  description: string;
  children?: ReactNode;
  compact?: boolean;
}

function EmptyResults({
  icon,
  title,
  description,
  children,
  compact = false,
}: EmptyResultsProps) {
  return (
    <Card
      className={
        compact
          ? "flex min-h-56 items-center justify-center border-dashed border-border bg-card/70"
          : "flex min-h-102.5 items-center justify-center border-dashed border-border bg-card/70"
      }
    >
      <CardContent className="flex flex-col items-center px-6 py-10 text-center">
        <div className="mb-5 flex size-20 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
          {icon}
        </div>

        <h3 className="text-lg font-semibold text-foreground">{title}</h3>

        <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>

        {children}
      </CardContent>
    </Card>
  );
}

function RecommendationLoading() {
  return (
    <div className="space-y-5" role="status">
      <span className="sr-only">Generating flight recommendations</span>

      <Card className="border-primary/20 bg-card">
        <CardContent className="flex items-center gap-4 p-5">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Radar className="size-6 animate-pulse" />
          </div>

          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-foreground">
              Running the recommendation pipeline
            </h3>

            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Discovering routes, validating aircraft and scoring eligible
              candidates.
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Card key={index} className="gap-0 border-border bg-card py-0">
            <CardContent className="space-y-3 p-4">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-3 w-24" />
            </CardContent>
          </Card>
        ))}
      </div>

      {Array.from({ length: 2 }, (_, index) => (
        <Card key={index} className="gap-0 border-border bg-card py-0">
          <CardContent className="space-y-5 p-5">
            <div className="flex items-center justify-between gap-3">
              <Skeleton className="h-3 w-32" />
              <Skeleton className="h-6 w-28 rounded-full" />
            </div>

            <div className="flex items-center justify-between gap-5">
              <div className="flex flex-1 items-center gap-5">
                <Skeleton className="h-12 w-20" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-12 w-20" />
              </div>

              <Skeleton className="size-16 shrink-0 rounded-full" />
            </div>

            <Skeleton className="h-px w-full" />

            <div className="flex flex-wrap gap-3">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-24" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function RecommendationResults({
  response,
  loading,
  aircraftPhotographyEnabled = false,
}: RecommendationResultsProps) {
  return (
    <section
      className="results-section min-w-0"
      aria-label="Flight recommendations"
      aria-busy={loading}
    >
      <div className="results-heading">
        <div>
          <div className="eyebrow">RECOMMENDATION ENGINE</div>

          <h2>Flight recommendations</h2>
        </div>

        {response && !loading && (
          <Badge
            variant="secondary"
            className="border border-primary/20 bg-primary/10 px-3 py-1.5 text-[10px] font-bold tracking-wide text-primary"
          >
            {response.returned.toLocaleString()} RESULTS
          </Badge>
        )}
      </div>

      {/* Initial empty state */}
      {!response && !loading && (
        <EmptyResults
          icon={<Waypoints size={34} strokeWidth={1.5} />}
          title="Ready for departure"
          description="Configure your flight parameters and generate recommendations to discover routes, evaluate aircraft compatibility and analyse flight scores."
        >
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <Badge variant="outline" className="gap-1.5">
              <ShieldCheck size={13} />
              Aircraft checks
            </Badge>

            <Badge variant="outline" className="gap-1.5">
              <Gauge size={13} />
              Flyability scoring
            </Badge>

            <Badge variant="outline" className="gap-1.5">
              <Terminal size={13} />
              Gate candidates
            </Badge>
          </div>
        </EmptyResults>
      )}

      {/* Loading */}
      {loading && <RecommendationLoading />}

      {/* Results */}
      {response && !loading && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <StatCard
              label="Generated"
              value={response.generated_candidates}
              description="Route candidates"
            />

            <StatCard
              label="Evaluated"
              value={response.evaluated_routes}
              description="Routes evaluated"
            />

            <StatCard
              label="Eligible flights"
              value={response.eligible_after_filters}
              description="After filters"
            />

            <StatCard
              label="Returned"
              value={response.returned}
              description="Recommended flights"
              accent
            />
          </div>

          {/* Engine warnings */}
          {response.warnings?.length > 0 && (
            <div className="space-y-2">
              {response.warnings.map((warning, index) => (
                <Alert
                  key={`${warning}-${index}`}
                  className="border-primary/20 bg-primary/5 text-foreground"
                >
                  <Info className="size-4 text-primary" />

                  <AlertDescription className="text-xs leading-relaxed text-muted-foreground">
                    {warning}
                  </AlertDescription>
                </Alert>
              ))}
            </div>
          )}
          {/* Departure Location */}
          {response.departure_location && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <MapPin className="size-4 shrink-0 text-primary" />

              <span>
                Departing from{""}
                <strong className="font-medium text-foreground">
                  {response.departure_location.display_name}
                </strong>
              </span>
            </div>
          )}

          {/* Recommended flights */}
          {response.recommendations.length > 0 ? (
            <div className="flight-list">
              {response.recommendations.map((item, index) => (
                <FlightCard
                  key={[
                    item.route.departure_icao,
                    item.route.arrival_icao,
                    item.route.aircraft_id,
                    index,
                  ].join("-")}
                  item={item}
                  index={index}
                  departureLocation={response.departure_location}
                  aircraftPhotographyEnabled={aircraftPhotographyEnabled}
                />
              ))}
            </div>
          ) : (
            <EmptyResults
              compact
              icon={<CircleAlert size={32} />}
              title="No matching routes"
              description="Try lowering minimum replayability, broadening airport discovery, increasing the candidate budget or allowing indeterminate aircraft checks."
            />
          )}

          {/* Existing decision trace */}
          <DecisionTracePanel
            key={response.request_id ?? "latest"}
            response={response}
          />
        </div>
      )}
    </section>
  );
}
