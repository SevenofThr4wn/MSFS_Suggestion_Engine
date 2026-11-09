import type { CSSProperties } from "react";
import { clampScore, cn, scoreClass } from "@/lib/utils";

interface ScoreRingProps {
  score: number;
  label: string;
  big?: boolean;
  className?: string;
}

export function ScoreRing({
  score,
  label,
  big = false,
  className,
}: ScoreRingProps) {
  const value = clampScore(score);
  const category = scoreClass(value);

  const colour =
    category === "high"
      ? "var(--green)"
      : category === "medium"
        ? "var(--primary)"
        : "#e5b773";

  const style = {
    background: `conic-gradient(${colour} ${value}%, var(--secondary) 0)`,
  } satisfies CSSProperties;

  return (
    <div
      className={cn(
        "grid shrink-0 place-items-center rounded-full p-1.25",
        big ? "size-28" : "size-19",
        className,
      )}
      style={style}
      role="img"
      aria-label={`${label}: ${Math.round(value)} out of 100`}
    >
      <div className="flex size-full flex-col items-center justify-center rounded-full bg-card text-center">
        <strong
          className={cn(
            "font-bold tabular-nums text-foreground",
            big ? "text-3xl" : "text-2xl",
          )}
        >
          {Math.round(value)}
        </strong>

        <span className="mt-0.5 max-w-[95%] px-1 text-center text-[7px] font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
      </div>
    </div>
  );
}
