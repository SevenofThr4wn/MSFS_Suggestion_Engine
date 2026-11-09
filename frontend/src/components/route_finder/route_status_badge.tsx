import { CheckCircle2, CircleHelp, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RouteSuitability } from "@/lib/types/route";

interface RouteStatusBadgeProps {
  status: RouteSuitability;
  showIcon?: boolean;
  compact?: boolean;
  className?: string;
}

const STATUS_CONFIG = {
  preliminary_pass: {
    label: "Preliminary Pass",
    shortLabel: "Pass",
    icon: CheckCircle2,
    className: "border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
  },

  indeterminate: {
    label: "Indeterminate",
    shortLabel: "Unknown",
    icon: CircleHelp,
    className: "border-amber-500/20 bg-amber-500/10 text-amber-400",
  },

  rejected: {
    label: "Rejected",
    shortLabel: "Rejected",
    icon: XCircle,
    className: "border-red-500/20 bg-red-500/10 text-red-400",
  },
} as const;

export default function RouteStatusBadge({
  status,
  showIcon = true,
  compact = false,
  className = "",
}: RouteStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.indeterminate;

  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      title={config.label}
      className={[
        "inline-flex w-fit items-center gap-1.5",
        "whitespace-nowrap rounded-md",
        "px-2 py-1 text-[10px]",
        "font-semibold tracking-wide",
        config.className,
        className,
      ].join(" ")}
    >
      {showIcon && <Icon className="size-3 shrink-0" />}

      {compact ? config.shortLabel : config.label}
    </Badge>
  );
}
