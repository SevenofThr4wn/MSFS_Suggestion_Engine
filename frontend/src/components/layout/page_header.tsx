import { ChevronRight, Radar } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { WorkspaceTab } from "@/lib/types/workspace";

interface PageHeaderProps {
  activeTab: WorkspaceTab;
}

export function PageHeader({ activeTab }: PageHeaderProps) {
  const pageLabel =
    activeTab === "explore" ? "ROUTE DISCOVERY" : "FLIGHT VALIDATION";

  return (
    <header className="flightengine-topbar flex h-18 items-center justify-between gap-4 border-b border-border bg-background/80 px-6 backdrop-blur-md lg:px-10">
      <div className="flex min-w-0 items-center gap-2 text-[10px] font-bold tracking-[0.13em] text-muted-foreground">
        <span className="hidden sm:inline">WORKSPACE</span>

        <ChevronRight className="hidden size-3.5 shrink-0 sm:inline" />

        <span className="truncate text-foreground">{pageLabel}</span>
      </div>

      <Badge
        variant="outline"
        className="hidden shrink-0 gap-2 border-primary/20 bg-primary/5 px-3 py-2 text-[10px] tracking-wide text-primary sm:inline-flex"
      >
        <Radar className="size-3.5" />
        ENGINE CONSOLE / BETA
      </Badge>
    </header>
  );
}
