// Colour scales for maps and legends. All colours come from theme tokens (src/styles/theme.css).
import { RAIN_CATEGORIES, rainCategory } from "@/lib/imd";
import type { Variable } from "@/lib/types";

export const SCALE_TOKENS: Record<Exclude<Variable, "rain">, string[]> = {
  tmax: ["--temp-1", "--temp-2", "--temp-3", "--temp-4", "--temp-5"],
  tmin: ["--temp-1", "--temp-2", "--temp-3", "--temp-4", "--temp-5"],
  rh: ["--rh-1", "--rh-2", "--rh-3", "--rh-4", "--rh-5"],
  wind: ["--wind-1", "--wind-2", "--wind-3", "--wind-4", "--wind-5"],
};

type RGB = [number, number, number];

function readToken(token: string): RGB {
  const v = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  const parts = v.split(/[\s,]+/).map(Number);
  return parts.length >= 3 && parts.every((n) => !Number.isNaN(n)) ? [parts[0], parts[1], parts[2]] : [128, 128, 128];
}

const rgb = ([r, g, b]: RGB) => `rgb(${Math.round(r)} ${Math.round(g)} ${Math.round(b)})`;

export interface Domain {
  min: number;
  max: number;
}

/**
 * Builds a colour function from the CURRENT theme tokens. Rebuild it after the theme changes.
 * Rain uses the IMD categories (discrete). Other variables interpolate across 5 stops over `domain`.
 */
export function makeColorScale(variable: Variable, domain: Domain): (value: number | null | undefined) => string {
  if (variable === "rain") {
    const colors = Object.fromEntries(RAIN_CATEGORIES.map((c) => [c.key, rgb(readToken(c.token))]));
    return (v) => colors[rainCategory(v ?? 0).key];
  }
  const stops = SCALE_TOKENS[variable].map(readToken);
  const span = domain.max - domain.min || 1;
  return (v) => {
    if (v === null || v === undefined) return "transparent";
    const t = Math.min(1, Math.max(0, (v - domain.min) / span)) * (stops.length - 1);
    const i = Math.min(stops.length - 2, Math.floor(t));
    const f = t - i;
    const [a, b] = [stops[i], stops[i + 1]];
    return rgb([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]);
  };
}

/** Shared domain across all days, panchayats and the block value, rounded outward, so colours stay
 *  comparable when switching days and both maps use exactly the same scale. */
export function niceDomain(values: number[], variable: Variable): Domain {
  const finite = values.filter((v) => Number.isFinite(v));
  if (!finite.length) return { min: 0, max: 1 };
  const step = variable === "rh" ? 5 : 1;
  let min = Math.floor(Math.min(...finite) / step) * step;
  let max = Math.ceil(Math.max(...finite) / step) * step;
  if (max === min) {
    min -= step;
    max += step;
  }
  return { min, max };
}

/** Text colour that stays readable on top of a fill colour. */
export function readableOn(fill: string): string {
  const m = fill.match(/rgb\((\d+)\s+(\d+)\s+(\d+)/);
  if (!m) return "#1D2A30";
  const [r, g, b] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.6 ? "rgb(29 42 48)" : "rgb(255 255 255)";
}
