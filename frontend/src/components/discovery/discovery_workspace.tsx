"use client";

import type { RecommendationsController } from "@/lib/hooks/useRecommendations";
import { useDisplayPreferences } from "@/lib/hooks/useDisplayPreferences";
import { RecommendationForm } from "./recommendation_form";
import { RecommendationResults } from "./recommendation_results";

interface DiscoveryWorkspaceProps {
  controller: RecommendationsController;
}

export function DiscoveryWorkspace({ controller }: DiscoveryWorkspaceProps) {
  const { aircraftPhotographyEnabled, setAircraftPhotographyEnabled } =
    useDisplayPreferences();

  return (
    <div className="workspace">
      <RecommendationForm
        controller={controller}
        aircraftPhotographyEnabled={aircraftPhotographyEnabled}
        onAircraftPhotographyChange={setAircraftPhotographyEnabled}
      />

      <RecommendationResults
        response={controller.response}
        loading={controller.loading}
        aircraftPhotographyEnabled={aircraftPhotographyEnabled}
      />
    </div>
  );
}
