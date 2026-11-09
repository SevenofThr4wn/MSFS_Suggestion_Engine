"use client";

import { useState } from "react";
import { useRecommendations } from "@/lib/hooks/useRecommendations";
import { useFlightValidation } from "@/lib/hooks/useFlightValidation";
import { Sidebar } from "@/components/layout/sidebar";
import { PageHeader } from "@/components/layout/page_header";
import { PageHeading } from "@/components/layout/page_heading";
import { DiscoveryWorkspace } from "@/components/discovery/discovery_workspace";
import { FlightValidator } from "@/components/validation/flight_validator";
import { Separator } from "@/components/ui/separator";
import { WorkspaceTab } from "@/lib/types/workspace";

export function Dashboard() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("explore");

  const recommendations = useRecommendations();
  const validation = useFlightValidation();

  function changeTab(tab: WorkspaceTab) {
    if (tab === activeTab) return;

    recommendations.clearError();
    validation.clearError();

    setActiveTab(tab);
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* Accessibility */}
      <a
        href="#main-content"
        className="sr-only fixed left-4 top-4 z-100 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground focus:not-sr-only"
      >
        Skip to main content
      </a>

      {/* Application sidebar */}
      <Sidebar activeTab={activeTab} onTabChange={changeTab} />

      {/* Main workspace */}
      <main
        id="main-content"
        className="flex min-h-screen min-w-0 flex-1 flex-col"
      >
        <PageHeader activeTab={activeTab} />

        <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col px-4 pb-8 pt-8 sm:px-6 lg:px-10 lg:pt-10">
          <PageHeading activeTab={activeTab} />

          {/* Keep both workspaces mounted to preserve UI state */}
          <div className="flex-1">
            <div
              id="route-discovery-workspace"
              hidden={activeTab !== "explore"}
              aria-hidden={activeTab !== "explore"}
            >
              <DiscoveryWorkspace controller={recommendations} />
            </div>

            <div
              id="flight-validation-workspace"
              hidden={activeTab !== "validate"}
              aria-hidden={activeTab !== "validate"}
            >
              <FlightValidator controller={validation} />
            </div>
          </div>

          {/* Application footer */}
          <footer className="mt-12">
            <Separator className="mb-5" />

            <div className="flex flex-col justify-between gap-3 text-[11px] text-muted-foreground sm:flex-row sm:items-center">
              <span className="font-semibold tracking-[0.12em]">
                FLIGHTENGINE / MSFS 2024
              </span>

              <span className="max-w-xl leading-relaxed">
                Screening results are simulator heuristics, not real-world
                dispatch approval.
              </span>
            </div>
          </footer>
        </div>
      </main>
    </div>
  );
}
