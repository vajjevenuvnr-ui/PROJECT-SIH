import { Cloud, CloudDrizzle, CloudRain, CloudRainWind, CloudSun, Sun, type LucideIcon } from "lucide-react";

/** Simple weather icon for a day (IMD rain categories first, then temperature). */
export function weatherIcon(rainMm: number, p10: number | null, tmax: number): LucideIcon {
  if (rainMm >= 64.5) return CloudRainWind;
  if (rainMm >= 15.6) return CloudRain;
  if (rainMm >= 2.5) return CloudDrizzle;
  if ((p10 ?? 0) >= 0.3 || rainMm > 0) return Cloud;
  if (tmax >= 36) return Sun;
  return CloudSun;
}

/** "38" / "12.3" / "+30" formatting for small numbers. */
export function num(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return String(Number(v.toFixed(decimals)));
}

export function signed(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined) return "–";
  const n = Number(v.toFixed(decimals));
  return n > 0 ? `+${n}` : String(n);
}
