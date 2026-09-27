"use client";

import { useMemo } from "react";
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cssColor, useTheme } from "@/components/theme/useTheme";
import { rainCategory } from "@/lib/imd";
import type { PanchayatDay } from "@/lib/types";

export interface ChartLabels {
  panchayat: string;
  block: string;
  tmax: string;
  tmin: string;
  rain: string;
  chance: string;
}

function usePalette() {
  const theme = useTheme();
  return useMemo(
    () => ({
      grid: cssColor("--color-border"),
      text: cssColor("--color-muted"),
      fg: cssColor("--color-foreground"),
      surface: cssColor("--color-surface"),
      hot: cssColor("--temp-5"),
      cold: cssColor("--temp-1"),
      accent: cssColor("--color-accent"),
      rain: (mm: number) => cssColor(rainCategory(mm).token),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme],
  );
}

const tooltipStyle = (p: ReturnType<typeof usePalette>) => ({
  contentStyle: {
    background: p.surface,
    border: `1px solid ${p.grid}`,
    borderRadius: 12,
    fontSize: 12,
    color: p.fg,
  },
  labelStyle: { color: p.fg, fontWeight: 700 },
});

/** Tmax/Tmin for the panchayat (solid) vs the IMD block value (dashed). */
export function TemperatureChart({ days, labels }: { days: PanchayatDay[]; labels: ChartLabels }) {
  const p = usePalette();
  const data = days.map((d) => ({
    name: d.weekday,
    tmax: d.tmax,
    tmin: d.tmin,
    btmax: d.block.tmax,
    btmin: d.block.tmin,
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
        <CartesianGrid stroke={p.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="name" tick={{ fill: p.text, fontSize: 12 }} axisLine={{ stroke: p.grid }} tickLine={false} />
        <YAxis tick={{ fill: p.text, fontSize: 12 }} axisLine={false} tickLine={false} domain={["dataMin - 1", "dataMax + 1"]} unit="°" />
        <Tooltip {...tooltipStyle(p)} formatter={(v) => `${v} °C`} />
        <Legend wrapperStyle={{ fontSize: 12, color: p.text }} iconType="plainline" />
        <Line type="monotone" dataKey="tmax" name={`${labels.tmax} · ${labels.panchayat}`} stroke={p.hot} strokeWidth={2.5} dot={{ r: 3 }} />
        <Line type="monotone" dataKey="tmin" name={`${labels.tmin} · ${labels.panchayat}`} stroke={p.cold} strokeWidth={2.5} dot={{ r: 3 }} />
        <Line type="monotone" dataKey="btmax" name={`${labels.tmax} · ${labels.block}`} stroke={p.hot} strokeDasharray="5 4" strokeOpacity={0.6} dot={false} />
        <Line type="monotone" dataKey="btmin" name={`${labels.tmin} · ${labels.block}`} stroke={p.cold} strokeDasharray="5 4" strokeOpacity={0.6} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Daily rain bars (coloured by IMD category) with P(>10 mm) and the block value. */
export function RainChart({ days, labels }: { days: PanchayatDay[]; labels: ChartLabels }) {
  const p = usePalette();
  const data = days.map((d) => ({
    name: d.weekday,
    rain: d.rain_mm,
    block: d.block.rain_mm,
    chance: d.rain_prob_10mm === null ? null : Math.round(d.rain_prob_10mm * 100),
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={data} margin={{ top: 8, right: 0, left: -12, bottom: 0 }}>
        <CartesianGrid stroke={p.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="name" tick={{ fill: p.text, fontSize: 12 }} axisLine={{ stroke: p.grid }} tickLine={false} />
        <YAxis yAxisId="mm" tick={{ fill: p.text, fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis yAxisId="pct" orientation="right" domain={[0, 100]} tick={{ fill: p.text, fontSize: 12 }} axisLine={false} tickLine={false} unit="%" />
        <Tooltip
          {...tooltipStyle(p)}
          formatter={(v, name) => (name === labels.chance ? `${v}%` : `${v} mm`)}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: p.text }} />
        <Bar yAxisId="mm" dataKey="rain" name={`${labels.rain} · ${labels.panchayat}`} fill={p.rain(20)} radius={[6, 6, 0, 0]} maxBarSize={38}>
          {data.map((d) => (
            <Cell key={d.name} fill={p.rain(d.rain)} stroke={p.grid} />
          ))}
        </Bar>
        <Line yAxisId="mm" type="stepAfter" dataKey="block" name={`${labels.rain} · ${labels.block}`} stroke={p.fg} strokeOpacity={0.55} strokeDasharray="5 4" dot={false} />
        <Line yAxisId="pct" type="monotone" dataKey="chance" name={labels.chance} stroke={p.accent} strokeWidth={2.5} dot={{ r: 3 }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
