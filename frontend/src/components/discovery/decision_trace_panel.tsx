"use client";

import { useId, useState } from "react";

import {
  Check,
  ChevronDown,
  ClipboardCopy,
  Code2,
  FileJson2,
  ShieldAlert,
} from "lucide-react";

import { cn, pretty } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

import { Separator } from "@/components/ui/separator";
import { RecommendationResponse } from "@/lib/types/recommendation";

interface DecisionTracePanelProps {
  response: RecommendationResponse;
}

interface JsonViewerProps {
  title: string;
  data: unknown;
  maxHeight?: number;
}

function JsonViewer({ title, data, maxHeight = 340 }: JsonViewerProps) {
  const [copied, setCopied] = useState(false);
  const formatted = pretty(data);

  async function copyJson() {
    try {
      await navigator.clipboard.writeText(formatted);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className="min-w-0 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <FileJson2 className="size-4 shrink-0 text-primary" />

          <h4 className="text-xs font-semibold text-foreground">{title}</h4>
        </div>

        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => void copyJson()}
          className="h-8 shrink-0 gap-2 text-xs text-muted-foreground hover:text-foreground"
        >
          {copied ? (
            <Check className="size-3.5" />
          ) : (
            <ClipboardCopy className="size-3.5" />
          )}
          {copied ? "Copied" : "Copy JSON"}
        </Button>
      </div>

      <div
        className={cn(
          "relative w-full min-w-0 overflow-hidden rounded-lg",
          "border border-border bg-[#080f1d]",
        )}
      >
        <div
          tabIndex={0}
          role="region"
          aria-label={`${title} JSON`}
          className="w-full min-w-0 overflow-auto overscroll-contain"
          style={{ maxHeight: `${maxHeight}px` }}
        >
          <pre className="m-0 w-max min-w-full p-4 font-mono text-[11px] leading-[1.8] text-[#b3c9e8]">
            <code>{formatted}</code>
          </pre>
        </div>
      </div>
    </section>
  );
}

export function DecisionTracePanel({ response }: DecisionTracePanelProps) {
  const [open, setOpen] = useState(false);
  const contentId = useId();

  const rejectedExamples = response.rejected_examples ?? [];

  const traceEvents = response.decision_trace?.events ?? [];

  const requestId =
    response.request_id ??
    response.decision_trace?.request_id ??
    "Not provided";

  return (
    <Card className="w-full min-w-0 gap-0 overflow-hidden border-border bg-card py-0">
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger
          className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition-colors hover:bg-secondary/30"
          aria-controls={contentId}
        >
          <span className="flex min-w-0 items-center gap-3">
            <Code2 className="size-4 shrink-0 text-primary" />

            <span className="text-sm font-semibold text-foreground">
              Engine diagnostics &amp; decision trace
            </span>
          </span>

          <ChevronDown
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform",
              open && "rotate-180",
            )}
          />
        </CollapsibleTrigger>

        <CollapsibleContent>
          <Separator />

          <CardContent id={contentId} className="min-w-0 space-y-6 p-5">
            {/* Request information */}
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0 space-y-2">
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
                  Request ID
                </p>

                <code className="block break-all text-xs text-foreground">
                  {requestId}
                </code>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge
                  variant="outline"
                  className="border-primary/20 bg-primary/5 text-primary"
                >
                  {traceEvents.length} trace events
                </Badge>

                <Badge variant="secondary" className="text-xs">
                  {rejectedExamples.length} rejected examples
                </Badge>
              </div>
            </div>

            <Separator />

            {/* Decision trace */}
            {response.decision_trace ? (
              <JsonViewer
                title="Decision trace"
                data={response.decision_trace}
                maxHeight={380}
              />
            ) : (
              <div className="rounded-lg border border-dashed border-border bg-secondary/20 p-5 text-center">
                <FileJson2 className="mx-auto mb-3 size-6 text-muted-foreground" />

                <p className="text-sm font-medium text-foreground">
                  No decision trace available
                </p>

                <p className="mt-2 text-xs text-muted-foreground">
                  Enable decision tracing in Advanced Settings to see how
                  recommendations are evaluated.
                </p>
              </div>
            )}

            {/* Rejected examples */}
            <section className="min-w-0 space-y-3">
              <div className="flex items-center gap-2">
                <ShieldAlert className="size-4 text-amber-400" />

                <h4 className="text-xs font-semibold text-foreground">
                  Rejected examples
                </h4>

                <Badge variant="outline">{rejectedExamples.length}</Badge>
              </div>

              {rejectedExamples.length > 0 ? (
                <JsonViewer
                  title="Rejected route data"
                  data={rejectedExamples}
                  maxHeight={280}
                />
              ) : (
                <div className="rounded-lg border border-border bg-secondary/20 px-4 py-5 text-center">
                  <p className="text-xs text-muted-foreground">
                    No rejected examples were returned by the recommendation
                    engine.
                  </p>
                </div>
              )}
            </section>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
