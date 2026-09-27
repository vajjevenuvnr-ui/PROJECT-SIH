"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cssColor, useTheme } from "@/components/theme/useTheme";

function usePalette() {
  const theme = useTheme();
  return useMemo(
    () => ({
      grid: cssColor("--color-border"),
      text: cssColor("--color-muted"),
      fg: cssColor("--color-foreground"),
      surface: cssColor("--color-surface"),
      block: cssColor("--color-accent"),
      ours: cssColor("--color-primary"),
      obs: cssColor("--color-foreground"),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme],
  );
}

const tt = (p: ReturnType<typeof usePalette>) => ({
  contentStyle: { background: p.surface, border: `1px solid ${p.grid}`, borderRadius: 12, fontSize: 12, color: p.fg },
  labelStyle: { color: p.fg, fontWeight: 700 },
});

export interface SeriesLabels {
  observed: string;
  block: string;
  ours: string;
}

/** Daily observed vs block vs Kshetra at one station. */
export function SeriesChart({
  dates,
  obs,
  block,
  ours,
  rain,
  labels,
  formatDate,
}: {
  dates: string[];
  obs: (number | null)[];
  block: (number | null)[];
  ours: (number | null)[];
  rain: boolean;
  labels: SeriesLabels;
  formatDate: (iso: string) => string;
}) {
  const p = usePalette();
  const data = dates.map((d, i) => ({ d, obs: obs[i], block: block[i], ours: ours[i] }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
        <CartesianGrid stroke={p.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="d" tickFormatter={formatDate} minTickGap={40} tick={{ fill: p.text, fontSize: 11 }} tickLine={false} axisLine={{ stroke: p.grid }} />
        <YAxis tick={{ fill: p.text, fontSize: 11 }} axisLine={false} tickLine={false} domain={rain ? [0, "auto"] : ["dataMin - 1", "dataMax + 1"]} />
        <Tooltip {...tt(p)} labelFormatter={(l) => formatDate(String(l))} />
        <Legend wrapperStyle={{ fontSize: 12, color: p.text }} />
        {rain ? (
          <Bar dataKey="obs" name={labels.observed} fill={p.obs} fillOpacity={0.35} maxBarSize={6} />
        ) : (
          <Line dataKey="obs" name={labels.observed} stroke={p.obs} strokeWidth={1.5} dot={false} connectNulls={false} />
        )}
        <Line dataKey="block" name={labels.block} stroke={p.block} strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
        <Line dataKey="ours" name={labels.ours} stroke={p.ours} strokeWidth={2} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/** Backtest event: observed vs block vs Kshetra (mm). */
export function BacktestChart({ observed, block, ours, labels }: { observed: number; block: number; ours: number; labels: SeriesLabels }) {
  const p = usePalette();
  const data = [
    { name: labels.observed, v: observed, c: p.obs },
    { name: labels.block, v: block, c: p.block },
    { name: labels.ours, v: ours, c: p.ours },
  ];
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 16, right: 8, left: -14, bottom: 0 }}>
        <CartesianGrid stroke={p.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="name" tick={{ fill: p.text, fontSize: 11 }} tickLine={false} axisLine={{ stroke: p.grid }} />
        <YAxis tick={{ fill: p.text, fontSize: 11 }} axisLine={false} tickLine={false} unit=" mm" />
        <Tooltip {...tt(p)} formatter={(v) => `${v} mm`} />
        <Bar dataKey="v" radius={[6, 6, 0, 0]} maxBarSize={56} label={{ position: "top", fill: p.fg, fontSize: 12, fontWeight: 700 }}>
          {data.map((d) => (
            <Cell key={d.name} fill={d.c} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Forecast vs observed Tmax with a 1:1 line, both methods. */
export function TmaxScatter({
  obs,
  block,
  ours,
  labels,
}: {
  obs: number[];
  block: number[];
  ours: number[];
  labels: SeriesLabels & { oneToOne: string };
}) {
  const p = usePalette();
  const lo = Math.floor(Math.min(...obs, ...block, ...ours));
  const hi = Math.ceil(Math.max(...obs, ...block, ...ours));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ScatterChart margin={{ top: 8, right: 8, left: -10, bottom: 8 }}>
        <CartesianGrid stroke={p.grid} strokeDasharray="3 3" />
        <XAxis type="number" dataKey="x" name={labels.observed} domain={[lo, hi]} unit="°" tick={{ fill: p.text, fontSize: 11 }} />
        <YAxis type="number" dataKey="y" domain={[lo, hi]} unit="°" tick={{ fill: p.text, fontSize: 11 }} />
        <Tooltip {...tt(p)} cursor={{ strokeDasharray: "3 3" }} />
        <Legend wrapperStyle={{ fontSize: 12, color: p.text }} />
        <ReferenceLine segment={[{ x: lo, y: lo }, { x: hi, y: hi }]} stroke={p.fg} strokeOpacity={0.5} strokeDasharray="4 4" ifOverflow="hidden" label={{ value: labels.oneToOne, fill: p.text, fontSize: 11, position: "insideTopLeft" }} />
        <Scatter name={labels.block} data={obs.map((x, i) => ({ x, y: block[i] }))} fill={p.block} fillOpacity={0.45} shape="circle" />
        <Scatter name={labels.ours} data={obs.map((x, i) => ({ x, y: ours[i] }))} fill={p.ours} fillOpacity={0.45} shape="circle" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
