import { CheckCircle2, CircleAlert, Code2, ShieldCheck } from "lucide-react";

import type { Recommendation } from "@/lib/types/recommendation";

import { clampScore, finite, pretty } from "@/lib/utils";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { MLAircraftSuggestions } from "./ml_aircraft_suggestions";

interface RecommendationAnalysisProps {
  item: Recommendation;
}

const FACTOR_MAXIMUMS: Record<string, number> = {
  scenery: 25,
  approach_experience: 20,
  airport_experience: 20,
  route_variety: 15,
  aircraft_enjoyment: 10,
  personal_replayability: 10,
};

function formatKey(key: string): string {
  return key.replaceAll("_", " ");
}

function ScoreBar({
  label,
  score,
}: {
  label: string;
  score: number | null | undefined;
}) {
  const available = typeof score === "number" && Number.isFinite(score);

  const value = available ? clampScore(score) : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="text-muted-foreground">{label}</span>

        <span className="font-semibold text-foreground">
          {available ? value.toFixed(1) : "N/A"}
        </span>
      </div>

      <Progress value={value} aria-label={`${label} score`} className="h-1.5" />
    </div>
  );
}

export function RecommendationAnalysis({ item }: RecommendationAnalysisProps) {
  const breakdown = Object.entries(item.route.flyability_breakdown ?? {});
  const evidence = Object.entries(item.evidence_coverage ?? {});
  const isPersonalised = item.route.flyability_status === "personalized";

  return (
    <div className="space-y-5 pt-3">
      <Card className="gap-4 border-border bg-secondary/30 py-5">
        <CardHeader className="px-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="text-sm font-semibold">
              Flight enjoyment &amp; replayability
            </CardTitle>

            <Badge variant="secondary">
              {isPersonalised ? "PERSONALISED" : "ESTIMATED"}
            </Badge>
          </div>

          <p className="text-xs leading-relaxed text-muted-foreground">
            How enjoyable this flight may be, and whether you would want to fly
            it again.
          </p>
        </CardHeader>

        <CardContent className="space-y-4 px-5">
          {breakdown.length > 0 ? (
            breakdown.map(([factor, points]) => {
              const maximum = FACTOR_MAXIMUMS[factor] ?? 100;
              const safePoints = finite(points);
              const percentage = clampScore((safePoints / maximum) * 100);
              const supported =
                item.route.flyability_evidence?.[factor] === true;

              return (
                <div key={factor} className="space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="capitalize text-foreground">
                        {formatKey(factor)}
                      </span>

                      {!supported && (
                        <span className="text-[10px] text-muted-foreground">
                          · estimated
                        </span>
                      )}
                    </div>

                    <span className="font-semibold tabular-nums text-foreground">
                      {safePoints.toFixed(1)} / {maximum}
                    </span>
                  </div>

                  <Progress
                    value={percentage}
                    aria-label={`${formatKey(factor)} contribution`}
                    className="h-1.5"
                  />
                </div>
              );
            })
          ) : (
            <p className="text-xs text-muted-foreground">
              No detailed replayability breakdown was returned.
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="gap-4 border-border bg-card py-5">
        <CardHeader className="px-5">
          <CardTitle className="text-sm">Recommendation scores</CardTitle>
        </CardHeader>

        <CardContent className="grid gap-5 px-5 sm:grid-cols-2">
          <ScoreBar label="Preference" score={item.preference_score} />

          <ScoreBar label="Realism" score={item.realism_score} />

          <ScoreBar
            label="History novelty"
            score={item.history_novelty_score}
          />

          <ScoreBar label="Weather" score={item.weather_score} />
        </CardContent>
      </Card>

      {item.reasons?.length > 0 && (
        <section className="space-y-3">
          <h4 className="flex items-center gap-2 text-xs font-semibold text-foreground">
            <ShieldCheck className="size-4 text-emerald-400" />
            Why this route was recommended
          </h4>

          <div className="space-y-2">
            {item.reasons.map((reason, index) => (
              <div
                key={index}
                className="flex items-start gap-2 rounded-lg border border-border bg-secondary/20 p-3 text-xs leading-relaxed text-muted-foreground"
              >
                <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-400" />
                {reason}
              </div>
            ))}
          </div>
        </section>
      )}

      {(item.warnings?.length ?? 0) > 0 && (
        <section className="space-y-3">
          <h4 className="flex items-center gap-2 text-xs font-semibold text-foreground">
            <CircleAlert className="size-4 text-amber-400" />
            Warnings
          </h4>

          {(item.warnings ?? []).map((warning, index) => (
            <Alert key={index} className="border-amber-500/25 bg-amber-500/5">
              <CircleAlert className="size-4 text-amber-400" />

              <AlertDescription className="text-xs leading-relaxed text-muted-foreground">
                {warning}
              </AlertDescription>
            </Alert>
          ))}
        </section>
      )}

      {evidence.length > 0 && (
        <section className="space-y-3">
          <h4 className="text-xs font-semibold text-foreground">
            Evidence coverage
          </h4>

          <div className="flex flex-wrap gap-2" aria-label="Evidence coverage">
            {evidence.map(([key, available]) => (
              <Badge
                key={key}
                variant="outline"
                className={
                  available
                    ? "gap-1.5 border-emerald-500/25 text-emerald-300"
                    : "gap-1.5 border-border text-muted-foreground"
                }
              >
                <span aria-hidden="true">{available ? "●" : "○"}</span>

                {formatKey(key)}
              </Badge>
            ))}
          </div>
        </section>
      )}

      {/* Machine learning aircraft predictions */}
      <section className="min-w-0 space-y-3">
        <MLAircraftSuggestions route={item.route} />
      </section>

      <Separator />

      {/* Full recommendation data */}
      <details className="group min-w-0 overflow-hidden rounded-lg border border-border bg-secondary/20">
        <summary className="flex cursor-pointer items-center gap-2 p-3 text-xs font-semibold text-primary">
          <Code2 className="size-4" />
          Full recommendation JSON
        </summary>

        <div className="max-h-110 min-w-0 overflow-auto border-t border-border">
          <pre className="m-0 w-max min-w-full p-4 text-[11px] leading-relaxed text-muted-foreground">
            {pretty(item)}
          </pre>
        </div>
      </details>
    </div>
  );
}
