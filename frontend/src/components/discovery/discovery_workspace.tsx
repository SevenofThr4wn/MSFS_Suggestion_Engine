"use client";

import type { RecommendationsController } from "@/lib/hooks/useRecommendations";
import { RecommendationForm } from "./recommendation_form";
import { RecommendationResults } from "./recommendation_results";

interface DiscoveryWorkspaceProps {
  controller: RecommendationsController;
}

export function DiscoveryWorkspace({ controller }: DiscoveryWorkspaceProps) {
  
  return (
    <div className="workspace">
      <RecommendationForm
        controller={controller}
      />

      <RecommendationResults
        response={controller.response}
        loading={controller.loading}
      />
    </div>
  );
}
