"use client";

import { Compass, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import SurpriseMeButton from "./suprise_me_button";

interface RouteFinderHeaderProps {
  loading: boolean;
  routeCount: number;

  onRefresh: () => void;
  onSurprise: () => void;

  surpriseDisabled: boolean;
}

export default function RouteFinderHeader({
  loading,
  routeCount,
  onRefresh,
  onSurprise,
  surpriseDisabled,
}: RouteFinderHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 bg-[#0e0f13] px-6 py-5">
      <div className="flex items-start gap-3">
        <div className="flex size-10 items-center justify-center rounded-xl border border-amber-400/20 bg-amber-400/10">
          <Compass className="size-5 text-amber-400" />
        </div>

        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-white">
              Route Finder
            </h1>

            <Badge
              variant="outline"
              className="border-white/10 bg-white/5 text-[10px] font-medium text-zinc-400"
            >
              DISCOVERY
            </Badge>
          </div>

          <p className="mt-1 text-sm text-zinc-500">
            Find your next flight across the world.
          </p>

          <p className="mt-2 text-xs text-zinc-600">
            {routeCount.toLocaleString()} recommendations loaded
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={onRefresh}
          disabled={loading}
          className="h-9 gap-2 rounded-full border-white/10 bg-white/4 text-zinc-300 hover:bg-white/8 hover:text-white"
        >
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>

        <SurpriseMeButton onClick={onSurprise} disabled={surpriseDisabled} />
      </div>
    </header>
  );
}
