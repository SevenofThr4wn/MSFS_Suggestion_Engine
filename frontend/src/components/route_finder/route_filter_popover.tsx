"use client";

import type { ReactNode } from "react";
import { Popover } from "@base-ui/react/popover";
import { ChevronDown, Plus } from "lucide-react";

interface RouteFilterPopoverProps {
  label: string;
  description?: string;
  active?: boolean;
  activeCount?: number;
  disabled?: boolean;
  children: ReactNode;
}

export default function RouteFilterPopover({
  label,
  description,
  active = false,
  activeCount = 0,
  disabled = false,
  children,
}: RouteFilterPopoverProps) {
  const isActive = active || activeCount > 0;

  return (
    <Popover.Root>
      <Popover.Trigger
        disabled={disabled}
        className={[
          "inline-flex h-9 shrink-0 items-center gap-2",
          "rounded-full border px-3 text-xs font-medium",
          "transition-colors outline-none",
          "focus-visible:ring-2 focus-visible:ring-amber-400",
          "disabled:cursor-not-allowed disabled:opacity-40",
          isActive
            ? "border-amber-400/40 bg-amber-400/10 text-amber-300"
            : "border-white/10 bg-white/4 text-zinc-300 hover:border-white/20 hover:bg-white/[0.07]",
        ].join(" ")}
      >
        {isActive ? (
          <span className="flex size-4 items-center justify-center rounded-full bg-amber-400 text-[10px] font-bold text-zinc-950">
            {activeCount > 0 ? activeCount : "✓"}
          </span>
        ) : (
          <Plus className="size-3.5 text-zinc-500" />
        )}

        <span>{label}</span>

        <ChevronDown className="size-3 text-zinc-500" />
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Positioner
          side="bottom"
          align="start"
          sideOffset={8}
          collisionPadding={12}
          className="z-50"
        >
          <Popover.Popup
            className={[
              "w-[min(340px,calc(100vw-24px))]",
              "rounded-xl border border-white/10",
              "bg-[#18191f] p-4 text-zinc-100",
              "shadow-2xl shadow-black/50 outline-none",
            ].join(" ")}
          >
            <div className="mb-4">
              <Popover.Title className="text-sm font-semibold text-white">
                {label}
              </Popover.Title>

              {description && (
                <Popover.Description className="mt-1 text-xs leading-5 text-zinc-500">
                  {description}
                </Popover.Description>
              )}
            </div>

            <div className="space-y-4">{children}</div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
