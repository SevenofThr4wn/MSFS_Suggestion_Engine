"use client";

import { useEffect, useState } from "react";

import {
  ChevronRight,
  ClipboardCheck,
  Compass,
  Menu,
  Plane,
  X,
} from "lucide-react";


import { cn } from "@/lib/utils";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { WorkspaceTab } from "@/lib/types/workspace";

interface SidebarProps {
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
}

const NAVIGATION = [
  {
    id: "explore",
    label: "Discover Routes",
    description: "Find your next flight",
    icon: Compass,
  },
  {
    id: "validate",
    label: "Flight Validator",
    description: "Aircraft compatibility",
    icon: ClipboardCheck,
  },
] as const;

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!mobileOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMobileOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileOpen]);

  function navigate(tab: WorkspaceTab) {
    onTabChange(tab);
    setMobileOpen(false);
  }

  const navigation = (
    <>
      <div className="flex items-center gap-3 px-3 pb-8 pt-2">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-blue-600 to-sky-400 text-white shadow-lg shadow-blue-500/10">
          <Plane className="size-5" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-sm font-extrabold tracking-[0.12em] text-foreground">
            FLIGHTENGINE
          </p>

          <p className="mt-1 text-[10px] font-semibold tracking-[0.12em] text-muted-foreground">
            ROUTE ENGINE
          </p>
        </div>
      </div>

      <div className="px-3">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[10px] font-bold tracking-[0.15em] text-muted-foreground">
            WORKSPACE
          </p>

          <Badge variant="outline" className="text-[9px] tracking-wide">
            BETA
          </Badge>
        </div>

        <nav aria-label="FlightEngine tools" className="space-y-1">
          {NAVIGATION.map((item) => {
            const active = activeTab === item.id;
            const Icon = item.icon;

            return (
              <Button
                key={item.id}
                type="button"
                variant="ghost"
                onClick={() => navigate(item.id)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "h-auto w-full justify-start gap-3 rounded-lg px-3 py-3 text-left transition-colors",
                  active
                    ? "border border-primary/25 bg-primary/15 text-foreground hover:bg-primary/20"
                    : "border border-transparent text-muted-foreground hover:bg-secondary hover:text-foreground",
                )}
              >
                <Icon
                  className={cn(
                    "size-4.5 shrink-0",
                    active && "text-primary",
                  )}
                />

                <span className="flex min-w-0 flex-1 flex-col items-start gap-1">
                  <span className="text-xs font-semibold">{item.label}</span>

                  <span className="text-[10px] font-normal text-muted-foreground">
                    {item.description}
                  </span>
                </span>

                {active && (
                  <ChevronRight className="size-4 shrink-0 text-primary" />
                )}
              </Button>
            );
          })}
        </nav>
      </div>

      <div className="mt-auto px-3 pb-2 pt-8">
        <Separator className="mb-5" />

        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span
              aria-hidden="true"
              className="size-2 rounded-full bg-slate-500"
            />
            FastAPI endpoint configured
          </div>

          <p className="text-[11px] leading-relaxed text-muted-foreground">
            MSFS 2024 · Engine Dashboard
            <span className="block">For Flight Simulator Use Only. NOT FOR REAL WORLD USE!</span>
          </p>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className="flightengine-sidebar hidden shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex"
        aria-label="Workspace navigation"
      >
        {navigation}
      </aside>

      {/* Mobile menu button */}
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="flightengine-mobile-menu fixed left-3 top-3 z-40 md:hidden"
        aria-label="Open navigation"
        aria-expanded={mobileOpen}
        aria-controls="flightengine-mobile-navigation"
        onClick={() => setMobileOpen(true)}
      >
        <Menu className="size-5" />
      </Button>

      {/* Mobile navigation overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setMobileOpen(false);
            }
          }}
        >
          <button
            type="button"
            className="absolute inset-0 bg-black/70"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          />

          <aside
            id="flightengine-mobile-navigation"
            role="dialog"
            aria-modal="true"
            aria-label="FlightEngine navigation"
            className="relative flex h-full w-[min(86vw,320px)] flex-col border-r border-border bg-sidebar px-4 py-6 shadow-2xl"
          >
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Close navigation"
              className="absolute right-3 top-3"
              onClick={() => setMobileOpen(false)}
            >
              <X className="size-5" />
            </Button>

            {navigation}
          </aside>
        </div>
      )}
    </>
  );
}
