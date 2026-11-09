"use client";

import { useId } from "react";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  hint?: string;
  disabled?: boolean;
  className?: string;
}

export function Toggle({
  label,
  checked,
  onChange,
  hint,
  disabled = false,
  className,
}: ToggleProps) {
  const id = useId();
  const descriptionId = hint ? `${id}-description` : undefined;

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-4 py-3",
        disabled && "opacity-50",
        className,
      )}
    >
      <div className="min-w-0 flex-1 space-y-1">
        <label
          htmlFor={id}
          className="block cursor-pointer text-xs font-semibold text-foreground"
        >
          {label}
        </label>

        {hint && (
          <p
            id={descriptionId}
            className="text-xs leading-relaxed text-muted-foreground"
          >
            {hint}
          </p>
        )}
      </div>

      <Switch
        id={id}
        checked={checked}
        onCheckedChange={onChange}
        disabled={disabled}
        aria-describedby={descriptionId}
      />
    </div>
  );
}
