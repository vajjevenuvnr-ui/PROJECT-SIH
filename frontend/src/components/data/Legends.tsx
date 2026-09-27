import { RAIN_CATEGORIES, TEMP_TOKENS, tokenColor } from "@/lib/imd";

/** IMD rainfall categories. `labels` maps category key -> localized name. */
export function RainLegend({ labels, note }: { labels?: Record<string, string>; note?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex overflow-hidden rounded-md border">
        {RAIN_CATEGORIES.map((c) => (
          <div key={c.key} className="h-3 flex-1" style={{ background: tokenColor(c.token) }} />
        ))}
      </div>
      <div className="flex text-[11px] text-muted">
        {RAIN_CATEGORIES.map((c) => (
          <div key={c.key} className="min-w-0 flex-1 pr-1">
            <div className="font-semibold text-foreground">{c.min}</div>
            <div className="truncate leading-tight">{labels?.[c.key] ?? c.label}</div>
          </div>
        ))}
      </div>
      <div className="text-[11px] text-muted">{note ?? "mm/day, IMD rainfall categories"}</div>
    </div>
  );
}

/** Continuous gradient legend over a domain (temperature, RH, wind). */
export function ContinuousLegend({
  tokens,
  min,
  max,
  unit,
  note,
}: {
  tokens: string[];
  min: number;
  max: number;
  unit: string;
  note?: string;
}) {
  const gradient = `linear-gradient(to right, ${tokens.map(tokenColor).join(", ")})`;
  const fmt = (v: number) => `${Math.round(v * 10) / 10}${unit === "%" ? "" : " "}${unit}`;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="h-3 rounded-md border" style={{ background: gradient }} />
      <div className="flex justify-between text-[11px] font-semibold text-foreground">
        <span>{fmt(min)}</span>
        <span>{fmt((min + max) / 2)}</span>
        <span>{fmt(max)}</span>
      </div>
      {note && <div className="text-[11px] text-muted">{note}</div>}
    </div>
  );
}

export function TempLegend({ min = 18, max = 42 }: { min?: number; max?: number }) {
  return <ContinuousLegend tokens={TEMP_TOKENS} min={min} max={max} unit="°C" />;
}
