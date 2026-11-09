import { clampScore } from "@/lib/utils";

interface MeterProps {
  label: string;
  score: number | null;
  suffix?: string;
}

export function Meter({ label, score, suffix = "/ 100" }: MeterProps) {
  const value = score === null || !Number.isFinite(score) ? null : clampScore(score);

  return (
    <div className="meter">
      <div className="meter-line">
        <span>{label}</span>
        <b>{value === null ? "N/A" : `${Math.round(value)} ${suffix}`}</b>
      </div>
      <div className="track" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value ?? undefined}>
        <span style={{ width: `${value ?? 0}%` }} />
      </div>
    </div>
  );
}
