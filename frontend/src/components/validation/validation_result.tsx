import {
  ArrowRight,
  BadgeCheck,
  CircleAlert,
  Info,
  ShieldCheck,
} from "lucide-react";

import type { ValidationResponse } from "@/lib/types/validation";

import { finite, pretty, statusLabel } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";

interface ValidationResultProps {
  result: ValidationResponse | null;
  loading: boolean;
}

function ValidationSkeleton() {
  return (
    <Card className="border-border bg-card">
      <CardHeader className="space-y-3">
        <Skeleton className="h-3 w-44" />

        <div className="flex items-center gap-5">
          <Skeleton className="h-12 w-24" />
          <Skeleton className="h-5 w-12" />
          <Skeleton className="h-12 w-24" />
        </div>

        <Skeleton className="h-4 w-56" />
      </CardHeader>

      <CardContent className="space-y-5">
        <Skeleton className="h-9 w-44 rounded-full" />
        <Separator />
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-20 w-full rounded-lg" />
      </CardContent>
    </Card>
  );
}

function ValidationEmpty() {
  return (
    <Card className="flex min-h-87.5 items-center justify-center border-dashed border-border bg-card/70">
      <CardContent className="flex flex-col items-center px-6 py-10 text-center">
        <div className="mb-5 flex size-20 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
          <ShieldCheck size={34} strokeWidth={1.5} />
        </div>

        <h3 className="text-lg font-semibold text-foreground">
          Test the impossible
        </h3>

        <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted-foreground">
          Try validating a Boeing 777-300ER between JFK and Saint Barthélemy
          (TFFJ) to explore runway suitability and aircraft compatibility
          warnings.
        </p>
      </CardContent>
    </Card>
  );
}

export function ValidationResult({ result, loading }: ValidationResultProps) {
  if (loading) {
    return (
      <div
        className="validation-results"
        role="status"
        aria-label="Validating flight"
      >
        <ValidationSkeleton />
      </div>
    );
  }

  if (!result) {
    return (
      <div className="validation-results">
        <ValidationEmpty />
      </div>
    );
  }

  const status = result.validation.status;

  const rejected = status === "rejected";
  const passed = status === "preliminary_pass";

  const statusStyles = rejected
    ? "border-red-500/30 bg-red-500/10 text-red-300"
    : passed
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : "border-amber-500/30 bg-amber-500/10 text-amber-300";

  const issues = result.validation.issues ?? [];

  const distance = finite(result.route_distance_nm).toLocaleString(undefined, {
    maximumFractionDigits: 0,
  });

  return (
    <div className="validation-results">
      <Card className="gap-5 border-border bg-card py-6">
        <CardHeader className="space-y-5 px-6">
          <div className="text-[10px] font-bold tracking-[0.15em] text-muted-foreground">
            AIRCRAFT VALIDATION RESULT
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <strong className="text-3xl font-bold tracking-tight text-foreground">
              {result.departure_icao}
            </strong>

            <ArrowRight className="size-6 text-primary" />

            <strong className="text-3xl font-bold tracking-tight text-foreground">
              {result.arrival_icao}
            </strong>
          </div>

          <CardTitle className="text-sm font-medium text-muted-foreground">
            {result.aircraft_name} · {distance} NM
          </CardTitle>

          <div>
            <Badge
              variant="outline"
              className={`gap-2 px-3 py-2 text-xs ${statusStyles}`}
            >
              {rejected ? (
                <CircleAlert className="size-4" />
              ) : (
                <BadgeCheck className="size-4" />
              )}

              {statusLabel(status)}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="space-y-5 px-6">
          <Separator />

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-foreground">
              Validation findings
            </h3>

            {issues.length === 0 ? (
              <Alert className="border-border bg-secondary/20">
                <Info className="size-4 text-primary" />

                <AlertDescription className="text-xs text-muted-foreground">
                  No validation issues were returned. This does not replace a
                  real-world operational performance calculation.
                </AlertDescription>
              </Alert>
            ) : (
              <div className="space-y-3">
                {issues.map((issue, index) => (
                  <Alert
                    key={`${issue.code}-${index}`}
                    className={
                      issue.severity === "reject" || rejected
                        ? "border-red-500/25 bg-red-500/5"
                        : "border-amber-500/25 bg-amber-500/5"
                    }
                  >
                    <CircleAlert className="size-4 text-amber-400" />

                    <AlertTitle className="text-xs font-semibold">
                      {issue.code.replaceAll("_", " ")}
                    </AlertTitle>

                    {issue.message && (
                      <AlertDescription className="text-xs leading-relaxed text-muted-foreground">
                        {issue.message}
                      </AlertDescription>
                    )}

                    {(issue.observed != null || issue.required != null) && (
                      <div className="mt-3 flex flex-wrap gap-4 text-[11px] text-muted-foreground">
                        {issue.observed != null && (
                          <span>
                            Observed:{" "}
                            <strong className="text-foreground">
                              {issue.observed} {issue.unit ?? ""}
                            </strong>
                          </span>
                        )}

                        {issue.required != null && (
                          <span>
                            Required:{" "}
                            <strong className="text-foreground">
                              {issue.required} {issue.unit ?? ""}
                            </strong>
                          </span>
                        )}
                      </div>
                    )}
                  </Alert>
                ))}
              </div>
            )}
          </section>

          {(result.validation.departure_runway ||
            result.validation.arrival_runway) && (
            <>
              <Separator />

              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-foreground">
                  Runway references
                </h3>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-border bg-secondary/20 p-3">
                    <p className="text-xs text-muted-foreground">Departure</p>

                    <p className="mt-2 text-sm font-semibold">
                      {result.validation.departure_runway ?? "Unknown"}
                    </p>
                  </div>

                  <div className="rounded-lg border border-border bg-secondary/20 p-3">
                    <p className="text-xs text-muted-foreground">Arrival</p>

                    <p className="mt-2 text-sm font-semibold">
                      {result.validation.arrival_runway ?? "Unknown"}
                    </p>
                  </div>
                </div>
              </section>
            </>
          )}

          <Separator />

          <details className="rounded-lg border border-border bg-secondary/20">
            <summary className="cursor-pointer p-3 text-xs font-semibold text-primary">
              Full validation JSON
            </summary>

            <pre className="max-h-105 overflow-auto border-t border-border p-4 text-[11px] leading-relaxed text-muted-foreground">
              {pretty(result)}
            </pre>
          </details>

          {result.disclaimer && (
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {result.disclaimer}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
