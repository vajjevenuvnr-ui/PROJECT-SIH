"use client";

import * as Popover from "@radix-ui/react-popover";
import { AlertTriangle, ArrowLeft, ArrowRight, Droplets, HelpCircle, Mountain, Users, Wind } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import Link from "next/link";

import { LEVEL_STYLE } from "@/components/alerts/AlertCenter";
import { ConfidencePill } from "@/components/data/ConfidencePill";
import { useApi } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import { localName } from "@/lib/names";
import type { Lang, PanchayatDay, PanchayatForecast } from "@/lib/types";
import { cn } from "@/lib/utils";
import { num, signed, weatherIcon } from "@/lib/weather";

const TemperatureChart = dynamic(() => import("@/components/charts/ForecastCharts").then((m) => m.TemperatureChart), {
  ssr: false,
  loading: () => <Skeleton className="h-60 w-full" />,
});
const RainChart = dynamic(() => import("@/components/charts/ForecastCharts").then((m) => m.RainChart), {
  ssr: false,
  loading: () => <Skeleton className="h-60 w-full" />,
});

export function PanchayatView({ panchayatId }: { panchayatId: number }) {
  const t = useTranslations("panchayat");
  const tc = useTranslations("confidence");
  const ta = useTranslations("alerts");
  const tr = useTranslations("rainCat");
  const locale = useLocale();
  const format = useFormatter();
  const { data, error, mutate } = useApi<PanchayatForecast>(`/api/forecast/panchayat/${panchayatId}`);

  if (error) return <ErrorCard message={error.message} onRetry={() => mutate()} />;
  if (!data) {
    return (
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <Skeleton className="h-24 w-full" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-52" />
          ))}
        </div>
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  const gp = data.panchayat;
  const name = localName(gp, locale);
  const weekday = (iso: string, style: "short" | "long" = "short") => format.dateTime(new Date(iso), { weekday: style });
  const dayMonth = (iso: string) => format.dateTime(new Date(iso), { day: "numeric", month: "short" });
  const localizedDays: PanchayatDay[] = data.days.map((d) => ({ ...d, weekday: weekday(d.date) }));
  const byDay = Object.fromEntries(data.days.map((d) => [d.day, d]));
  const chartLabels = {
    panchayat: t("panchayatLabel"),
    block: t("blockLabel"),
    tmax: t("tmax"),
    tmin: t("tmin"),
    rain: t("rain"),
    chance: t("chanceLabel"),
  };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      {/* Header */}
      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
        <div className="flex min-w-0 items-start gap-3">
          <Button asChild variant="ghost" size="sm" className="-ml-2 shrink-0">
            <Link href={`/block/${gp.block.id}?var=rain&day=2`}>
              <ArrowLeft /> {t("backToMap")}
            </Link>
          </Button>
          <div className="min-w-0">
            <h1 className="text-2xl font-bold leading-tight sm:text-3xl">
              {name}
              {name !== gp.name && <span className="ml-2 text-base font-medium text-muted">{gp.name}</span>}
            </h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
              <span>{t("block", { block: localName(gp.block, locale) })}</span>
              {gp.elevation_m !== null && (
                <span className="inline-flex items-center gap-1">
                  <Mountain className="h-3.5 w-3.5" aria-hidden /> {t("elevation", { m: Math.round(gp.elevation_m) })}
                </span>
              )}
              {gp.registered_farmers !== null && (
                <span className="inline-flex items-center gap-1">
                  <Users className="h-3.5 w-3.5" aria-hidden /> {t("farmers", { n: gp.registered_farmers })}
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ConfidencePill level={gp.confidence} label={tc(gp.confidence)} className="px-3 py-1 text-[11px]" />
          <Popover.Root>
            <Popover.Trigger asChild>
              <button
                type="button"
                aria-label={t("confTitle")}
                className="flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-surface-2 hover:text-foreground"
              >
                <HelpCircle className="h-4 w-4" />
              </button>
            </Popover.Trigger>
            <Popover.Portal>
              <Popover.Content
                align="end"
                sideOffset={8}
                className="z-[1100] w-72 rounded-xl border bg-surface p-4 text-sm shadow-card"
              >
                <p className="font-semibold">{t("confTitle")}</p>
                <p className="mt-1.5 text-muted">{t("confBody")}</p>
                <Popover.Arrow className="fill-surface" />
              </Popover.Content>
            </Popover.Portal>
          </Popover.Root>
        </div>
      </Card>

      {/* IMD colour-coded warnings (Phase 6b) */}
      {(data.warnings ?? []).map((w) => (
        <div key={w.id} role="alert" className={cn("flex flex-col gap-1 rounded-card px-4 py-3 shadow-card", LEVEL_STYLE[w.level])}>
          <p className="flex flex-wrap items-center gap-2 text-base font-extrabold">
            <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden />
            {w.title[locale as Lang]} · {w.value} {w.unit} · {weekday(w.date, "long")}
          </p>
          <p className="text-sm font-semibold opacity-90">{w.actions[locale as Lang].join(" · ")}</p>
        </div>
      ))}

      {/* Alerts */}
      {data.alerts.map((a, i) => {
        const d = byDay[a.day];
        const p = d?.rain_prob_10mm !== null && d?.rain_prob_10mm !== undefined ? Math.round(d.rain_prob_10mm * 100) : null;
        return (
          <div
            key={i}
            role="alert"
            className={cn(
              "flex items-center gap-3 rounded-card border-l-4 px-4 py-3 font-semibold",
              a.severity === "warning" ? "border-danger bg-danger/10 text-danger" : "border-accent bg-accent/15 text-foreground",
            )}
          >
            <AlertTriangle className={cn("h-5 w-5 shrink-0", a.severity === "warning" ? "text-danger" : "text-warning")} aria-hidden />
            <span>
              {t("alertOn", {
                title: ta(`${a.type}.${a.severity}`),
                day: `${weekday(a.date, "long")}, ${dayMonth(a.date)}`,
                p: p ?? "–",
              })}
            </span>
          </div>
        );
      })}

      {/* Day cards */}
      <section aria-label={t("days")}>
        <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:grid-cols-5 sm:overflow-visible sm:px-0">
          {data.days.map((d) => {
            const Icon = weatherIcon(d.rain_mm, d.rain_prob_10mm, d.tmax);
            const rainDiff = d.diff.rain_mm ?? 0;
            const bigRainDiff = Math.abs(rainDiff) >= 5;
            const alerted = data.alerts.some((a) => a.day === d.day);
            return (
              <Card
                key={d.day}
                className={cn(
                  "flex min-w-[10.5rem] snap-start flex-col gap-2 p-4 sm:min-w-0",
                  alerted && "ring-2 ring-accent",
                )}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-bold">{weekday(d.date)}</p>
                    <p className="text-xs text-muted">{dayMonth(d.date)}</p>
                  </div>
                  <Icon className="h-8 w-8 text-info" aria-hidden />
                </div>
                <p className="text-2xl font-bold leading-none">
                  {num(d.tmax, 0)}°<span className="text-lg font-semibold text-muted">/{num(d.tmin, 0)}°</span>
                </p>
                <div title={d.rain_min !== null && d.rain_max !== null ? t("rangeHint", { min: d.rain_min, max: d.rain_max }) : undefined}>
                  <p className="text-lg font-bold leading-tight">
                    {num(d.rain_mm)} <span className="text-sm font-semibold">mm</span>
                  </p>
                  <p className="text-xs text-muted">{tr(d.rain_category.key)}</p>
                  {d.rain_prob_10mm !== null && (
                    <p className="mt-0.5 text-xs font-semibold text-info">
                      {t("chance10", { p: Math.round(d.rain_prob_10mm * 100) })}
                    </p>
                  )}
                </div>
                <div className="flex gap-3 text-xs text-muted">
                  <span className="inline-flex items-center gap-1" title={t("rh")}>
                    <Droplets className="h-3.5 w-3.5" aria-hidden /> {num(d.rh, 0)}%
                  </span>
                  <span className="inline-flex items-center gap-1" title={t("wind")}>
                    <Wind className="h-3.5 w-3.5" aria-hidden /> {num(d.wind_kmh, 0)} km/h
                  </span>
                </div>
                <div className="mt-auto rounded-lg bg-surface-2 px-2.5 py-1.5 text-xs">
                  <span className="text-muted">{t("vsBlock")}</span>
                  <div className="flex justify-between gap-2 font-semibold">
                    <span className={cn(bigRainDiff && "rounded bg-accent/25 px-1 text-foreground")}>
                      {signed(d.diff.rain_mm)} mm
                    </span>
                    <span>{signed(d.diff.tmax)}°</span>
                  </div>
                </div>
                <ConfidencePill level={d.confidence} label={tc(d.confidence)} className="self-start text-[9px]" />
              </Card>
            );
          })}
        </div>
      </section>

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("tempChart")}</CardTitle>
          </CardHeader>
          <CardContent>
            <TemperatureChart days={localizedDays} labels={chartLabels} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("rainChart")}</CardTitle>
          </CardHeader>
          <CardContent>
            <RainChart days={localizedDays} labels={chartLabels} />
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-end">
        <Button asChild size="lg" className="w-full sm:w-auto">
          <Link href={`/panchayat/${gp.id}/advisory`}>
            {t("generate")} <ArrowRight />
          </Link>
        </Button>
      </div>
    </div>
  );
}
