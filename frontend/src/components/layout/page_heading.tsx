import { WorkspaceTab } from "@/lib/types/workspace";

interface PageHeadingProps {
  activeTab: WorkspaceTab;
}

export function PageHeading({ activeTab }: PageHeadingProps) {
  const exploring = activeTab === "explore";

  return (
    <div className="mb-8 space-y-4">
      <div className="flex items-center gap-2 text-[10px] font-bold tracking-[0.16em] text-primary">
        <span aria-hidden="true" className="size-1.5 rounded-full bg-primary" />
        MSFS 2024 FLIGHT PLANNING SYSTEM
      </div>

      <h1 className="max-w-4xl text-3xl font-bold tracking-tight text-foreground sm:text-4xl lg:text-[42px]">
        {exploring
          ? "Discover your next flight."
          : "Check aircraft compatibility."}
      </h1>

      <p className="max-w-3xl text-sm leading-7 text-muted-foreground">
        {exploring
          ? "Intelligent routes, aircraft suitability, airport realism and explainable recommendations — one flight at a time."
          : "Test a specific aircraft and airport pair, including flights that would be filtered out of discovery."}
      </p>
    </div>
  );
}
