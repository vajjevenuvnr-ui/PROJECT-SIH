"use client";

import { AlertTriangle, ArrowDownRight, ArrowUpRight, FlaskConical, Info, Minus, Target } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

import { useApi } from "@/components/providers/AppProviders";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Improvement, MetricGroup, StationSeries, ValidationResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const StationMap = dynamic(() => import("@/components/validation/StationMap"), { ssr: false, loading: () => <Skeleton className="h-full w-full" /> });
const Charts = {
  Series: dynamic(() => import("@/components/validation/ValidationCharts").then((m) => m.SeriesChart), { ssr: false, loading: () => <Skeleton className="h-64 w-full" /> }),
  Backtest: dynamic(() => import("@/components/validation/ValidationCharts").then((m) => m.BacktestChart), { ssr: false, loading: () => <Skeleton className="h-48 w-full" /> }),
  Scatter: dynamic(() => import("@/components/validation/ValidationCharts").then((m) => m.TmaxScatter), { ssr: false, loading: () => <Skeleton className="h-72 w-full" /> }),
};

type Var = "tmax" | "tmin" | "rain";
type Verdict = "better" | "worse" | "neutral";

/** Verdict from a 90% CI of a % change. For error metrics lower is better; for skill scores higher is better. */
function verdict(imp: Improvement | undefined, lowerIsBetter: boolean): Verdict {
  const [lo, hi] = imp?.ci90 ?? [null, null];
  if (lo == null || hi == null) return "neutral";
  if (lowerIsBetter ? hi < 0 : lo > 0) return "better";
  if (lowerIsBetter ? lo > 0 : hi < 0) return "worse";
  return "neutral";
}

const TONE: Record<Verdict, string> = {
  better: "bg-success/15 text-success",
  worse: "bg-danger/15 text-danger",
  neutral: "bg-surface-2 text-muted",
};

function VerdictChip({ v, labels }: { v: Verdict; labels: Record<Verdict, string> }) {
  const Icon = v === "better" ? ArrowDownRight : v === "worse" ? ArrowUpRight : Minus;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold", TONE[v])}>
      <Icon className="h-3.5 w-3.5" aria-hidden /> {labels[v]}
    </span>
  );
}

function ScoreCard({
  label,
  hint,
  base,
  ours,
  unit,
  lowerIsBetter,
  closerToZero,
  labels,
}: {
  label: string;
  hint?: string;
  base: number | null | undefined;
  ours: number | null | undefined;
  unit?: string;
  lowerIsBetter: boolean;
  /** Bias: better when closer to zero. */
  closerToZero?: boolean;
  labels: { baseline: string; ours: string; lower: string; higher: string; zero?: string };
}) {
  const diff = base != null && ours != null ? (closerToZero ? Math.abs(ours) - Math.abs(base) : ours - base) : null;
  const good = diff == null || Math.abs(diff) < 1e-9 ? null : lowerIsBetter ? diff < 0 : diff > 0;
  return (
    <Card className="p-4" title={hint}>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">
        {label} <span className="font-normal normal-case">· {closerToZero ? labels.zero : lowerIsBetter ? labels.lower : labels.higher}</span>
      </p>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div>
          <p className="text-[11px] text-muted">{labels.baseline}</p>
          <p className="text-2xl font-extrabold text-muted">
            {base ?? "–"}
            {unit && <span className="text-sm font-semibold"> {unit}</span>}
          </p>
        </div>
        <div>
          <p className="text-[11px] text-muted">{labels.ours}</p>
          <p className={cn("text-2xl font-extrabold", good === true ? "text-success" : good === false ? "text-danger" : "text-foreground")}>
            {ours ?? "–"}
            {unit && <span className="text-sm font-semibold"> {unit}</span>}
          </p>
        </div>
      </div>
    </Card>
  );
}

export function ValidationView() {
  const t = useTranslations("validation");
  const format = useFormatter();
  const { data, error, mutate } = useApi<ValidationResponse>("/api/validation");
  const [variable, setVariable] = useState<Var>("tmax");
  const [threshold, setThreshold] = useState<number>(10);
  const [stationId, setStationId] = useState<string | number | null>(null);

  useEffect(() => {
    if (data?.stations.length && stationId == null) {
      const best = [...data.stations].sort((a, b) => (a.distance_km ?? 999) - (b.distance_km ?? 999))[0];
      setStationId(best.id);
    }
  }, [data, stationId]);
  const series = useApi<StationSeries>(stationId != null && data?.summary ? `/api/validation/station/${stationId}/series` : null);

  const group = useMemo<MetricGroup | undefined>(
    () => data?.metrics.find((m) => m.variable === variable && (variable !== "rain" || m.threshold_mm === threshold)),
    [data, variable, threshold],
  );
  const thresholds = useMemo(
    () => (data?.metrics.filter((m) => m.variable === "rain").map((m) => m.threshold_mm as number) ?? []).sort((a, b) => a - b),
    [data],
  );

  if (error) return <ErrorCard message={error.message} onRetry={() => mutate()} />;
  if (!data) {
    return (
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <Skeleton className="h-10 w-72" />
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  const s = data.summary;
  const labels = { baseline: t("baseline"), ours: t("ours"), lower: t("lowerBetter"), higher: t("higherBetter") };
  const vLabels = { better: t("better"), worse: t("worse"), neutral: t("noDiff") };
  const impKey = variable === "rain" ? `rain_csi_${threshold}` : variable;
  const imp = s?.improvements[impKey];
  const v = verdict(imp, variable !== "rain");
  const b = group?.block_baseline;
  const o = group?.panchayatcast;
  const station = data.stations.find((x) => x.id === stationId);
  const ev = data.backtest_events[0];
  const seriesVar: Var = variable;
  const dayMonth = (iso: string) => format.dateTime(new Date(iso), { day: "numeric", month: "short", year: "2-digit" });
  const serLabels = { observed: t("observed"), block: t("baseline"), ours: t("ours") };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold sm:text-3xl">{t("title")}</h1>
          <p className="mt-1 text-muted">{t("subtitle")}</p>
        </div>
        {group && <p className="text-sm text-muted">{t("period")}: <b className="text-foreground">{group.period}</b></p>}
      </div>

      {data.is_placeholder && (
        <p className="flex items-center gap-2 rounded-card border-l-4 border-accent bg-accent/15 px-4 py-3 text-sm font-semibold">
          <FlaskConical className="h-4 w-4 text-warning" aria-hidden /> {t("placeholder")}
        </p>
      )}

      {/* Controls */}
      <Card className="flex flex-wrap items-center gap-3 p-3">
        <div role="tablist" aria-label={t("variable")} className="flex gap-1">
          {(["tmax", "tmin", "rain"] as Var[]).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={variable === k}
              onClick={() => setVariable(k)}
              className={cn(
                "rounded-xl px-4 py-2 text-sm font-semibold transition-colors",
                variable === k ? "bg-primary text-primary-foreground" : "hover:bg-surface-2",
              )}
            >
              {t(`vars.${k}`)}
            </button>
          ))}
        </div>
        {variable === "rain" && thresholds.length > 0 && (
          <div role="radiogroup" aria-label={t("threshold")} className="flex items-center gap-1 text-sm">
            <span className="mr-1 text-muted">{t("threshold")}:</span>
            {thresholds.map((th) => (
              <button
                key={th}
                role="radio"
                aria-checked={threshold === th}
                onClick={() => setThreshold(th)}
                className={cn("rounded-full border px-3 py-1 font-semibold", threshold === th ? "border-primary bg-primary/10 text-primary" : "hover:bg-surface-2")}
              >
                ≥{th} mm
              </button>
            ))}
          </div>
        )}
        {group && (
          <span className="ml-auto text-xs text-muted">
            {t("samples", { n: group.n_samples ?? 0, s: group.n_stations ?? 0 })}
            {group.n_events != null && ` · ${t("events", { n: group.n_events })}`}
          </span>
        )}
      </Card>

      {/* KPI cards */}
      {variable === "rain" ? (
        o?.csi == null && o?.pod === 0 && b?.pod === 0 ? (
          <p className="text-sm text-muted">{t("noEvents")}</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-3">
            <ScoreCard label={t("pod")} hint={t("podHint")} base={b?.pod} ours={o?.pod} lowerIsBetter={false} labels={labels} />
            <ScoreCard label={t("far")} hint={t("farHint")} base={b?.far} ours={o?.far} lowerIsBetter labels={labels} />
            <ScoreCard label={t("csi")} hint={t("csiHint")} base={b?.csi} ours={o?.csi} lowerIsBetter={false} labels={labels} />
          </div>
        )
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <ScoreCard label={t("rmse")} base={b?.rmse} ours={o?.rmse} unit="°C" lowerIsBetter labels={labels} />
          <ScoreCard label={t("bias")} base={b?.bias} ours={o?.bias} unit="°C" lowerIsBetter closerToZero labels={{ ...labels, zero: t("zeroBetter") }} />
          <Card className="flex flex-col justify-center gap-2 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">{t("change")} ({t("rmse")})</p>
            <p className="text-3xl font-extrabold">{imp?.change_pct != null ? `${imp.change_pct > 0 ? "+" : ""}${imp.change_pct}%` : "–"}</p>
            {imp?.ci90?.[0] != null && <p className="text-xs text-muted">{t("ci", { lo: imp.ci90[0], hi: imp.ci90[1] ?? "" })}</p>}
            <VerdictChip v={v} labels={vLabels} />
          </Card>
        </div>
      )}
      {variable === "rain" && imp && (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <b>{t("csi")} {t("change")}:</b> {imp.change_pct != null ? `${imp.change_pct > 0 ? "+" : ""}${imp.change_pct}%` : "–"}
          {imp.ci90?.[0] != null && <span className="text-muted">({t("ci", { lo: imp.ci90[0], hi: imp.ci90[1] ?? "" })})</span>}
          <VerdictChip v={v} labels={vLabels} />
        </p>
      )}
      {s && variable === "rain" && (
        <p className="flex items-start gap-2 rounded-xl bg-surface-2 px-3 py-2 text-sm">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" aria-hidden />
          {t("wetDays", { n: s.wet_day_counts.wet_days, better: s.wet_day_counts.better, worse: s.wet_day_counts.worse, similar: s.wet_day_counts.similar })}
        </p>
      )}

      {/* Stations + series */}
      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="overflow-hidden lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("stations")}</CardTitle>
            <p className="text-xs text-muted">{t("stationsHint")}</p>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <StationMap
                stations={data.stations}
                metric={variable === "rain" ? "rain" : "tmax"}
                selected={stationId}
                onSelect={setStationId}
                labels={{ gajwel: "Gajwel", distance: (km) => t("distance", { km }), block: t("baseline"), ours: t("ours") }}
              />
            </div>
          </CardContent>
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>{station ? t("series", { name: station.name }) : t("stations")}</CardTitle>
            {station?.distance_km != null && <p className="text-xs text-muted">{t("distance", { km: station.distance_km })} · {station.source}</p>}
          </CardHeader>
          <CardContent>
            {series.data ? (
              <Charts.Series
                dates={series.data.dates}
                obs={series.data[`obs_${seriesVar}`] as (number | null)[]}
                block={series.data[`block_${seriesVar}`] as (number | null)[]}
                ours={series.data[`ours_${seriesVar}`] as (number | null)[]}
                rain={seriesVar === "rain"}
                labels={serLabels}
                formatDate={dayMonth}
              />
            ) : (
              <Skeleton className="h-64 w-full" />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Backtest + scatter */}
      <div className="grid gap-4 lg:grid-cols-2">
        {ev && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-4 w-4 text-primary" aria-hidden /> {t("backtest")}
              </CardTitle>
              <p className="text-sm text-muted">
                {t("backtestText", {
                  date: format.dateTime(new Date(ev.date), { day: "numeric", month: "long", year: "numeric" }),
                  station: ev.station_name ?? String(ev.station_id),
                  obs: ev.observed_mm,
                  block: ev.block_mm,
                  ours: ev.ours_mm,
                })}
              </p>
            </CardHeader>
            <CardContent>
              <Charts.Backtest observed={ev.observed_mm} block={ev.block_mm} ours={ev.ours_mm} labels={serLabels} />
            </CardContent>
          </Card>
        )}
        {s?.scatter_tmax && (
          <Card>
            <CardHeader>
              <CardTitle>{t("scatter")}</CardTitle>
            </CardHeader>
            <CardContent>
              <Charts.Scatter
                obs={s.scatter_tmax.obs}
                block={s.scatter_tmax.block}
                ours={s.scatter_tmax.ours}
                labels={{ ...serLabels, oneToOne: t("oneToOne") }}
              />
            </CardContent>
          </Card>
        )}
      </div>

      {/* Engine skill (model-to-model) */}
      {data.engine_skill?.holdout && (
        <Card className="p-4">
          <p className="font-semibold">{t("engine")}</p>
          <p className="text-xs text-muted">{t("engineHint")}</p>
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <span>{t("engineRow", { v: t("vars.tmax"), base: `${data.engine_skill.holdout.tmax.rmse_baseline}°C`, ours: `${data.engine_skill.holdout.tmax.rmse_model}°C` })}</span>
            <span>{t("engineRow", { v: t("vars.tmin"), base: `${data.engine_skill.holdout.tmin.rmse_baseline}°C`, ours: `${data.engine_skill.holdout.tmin.rmse_model}°C` })}</span>
            <span>{t("engineRain", { base: data.engine_skill.holdout.rain.heavy10_baseline.csi, ours: data.engine_skill.holdout.rain.heavy10_model.csi })}</span>
          </div>
        </Card>
      )}

      {/* Method + caveats */}
      <Card className="p-4 text-sm">
        <p className="font-semibold">{t("method")}</p>
        <p className="mt-1 text-muted">{s?.method_note ?? data.method_note}</p>
        {s?.caveats?.length ? (
          <>
            <p className="mt-3 flex items-center gap-1.5 font-semibold">
              <AlertTriangle className="h-4 w-4 text-warning" aria-hidden /> {t("caveats")}
            </p>
            <ul className="mt-1 list-disc pl-5 text-muted">
              {s.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </>
        ) : null}
      </Card>
    </div>
  );
}
