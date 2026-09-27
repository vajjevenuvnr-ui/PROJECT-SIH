"use client";

import {
  CloudRain,
  Droplets,
  FileDown,
  Info,
  Maximize2,
  Minimize2,
  MousePointerClick,
  ThermometerSnowflake,
  ThermometerSun,
  Wind,
  type LucideIcon,
} from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAlerts } from "@/components/alerts/AlertCenter";
import { ContinuousLegend, RainLegend } from "@/components/data/Legends";
import { useApi, useRegion } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import { rainCategory } from "@/lib/imd";
import { localName } from "@/lib/names";
import { SCALE_TOKENS, niceDomain } from "@/lib/scales";
import type { AlertLevel, Confidence, ForecastBundle, Variable } from "@/lib/types";
import { cn } from "@/lib/utils";

const SplitMap = dynamic(() => import("@/components/map/SplitMap"), {
  ssr: false,
  loading: () => (
    <div className="grid gap-3 md:grid-cols-2">
      <Skeleton className="h-[60vh] md:h-[calc(100vh-21rem)] md:min-h-[440px]" />
      <Skeleton className="hidden h-[calc(100vh-21rem)] min-h-[440px] md:block" />
    </div>
  ),
});

const VARIABLES: { key: Variable; icon: LucideIcon }[] = [
  { key: "rain", icon: CloudRain },
  { key: "tmax", icon: ThermometerSun },
  { key: "tmin", icon: ThermometerSnowflake },
  { key: "rh", icon: Droplets },
  { key: "wind", icon: Wind },
];

const UNITS: Record<Variable, string> = { rain: "mm", tmax: "°C", tmin: "°C", rh: "%", wind: "km/h" };

function isVariable(v: string | null): v is Variable {
  return !!v && VARIABLES.some((x) => x.key === v);
}

export function formatValue(v: number | null | undefined, variable: Variable): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const decimals = variable === "rh" ? 0 : 1;
  const n = Number(v.toFixed(decimals));
  const unit = UNITS[variable];
  return `${n}${unit === "%" ? "" : " "}${unit}`;
}

function useIsMobile() {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    const on = () => setMobile(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return mobile;
}

export function BlockMapView({ blockId }: { blockId: number }) {
  const t = useTranslations("blockMap");
  const tc = useTranslations("confidence");
  const tr = useTranslations("rainCat");
  const locale = useLocale();
  const format = useFormatter();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tb = useTranslations("bulletin");
  const { selection, setSelection } = useRegion();

  // Variable/day live in state (instant, no navigation); the URL mirrors them for sharing/refresh.
  const [variable, setVariable] = useState<Variable>(() =>
    isVariable(params.get("var")) ? (params.get("var") as Variable) : "rain",
  );
  const [day, setDay] = useState<number>(() => {
    const d = Number(params.get("day"));
    return d >= 1 && d <= 5 ? d : 1;
  });
  useEffect(() => {
    window.history.replaceState(null, "", `${pathname}?var=${variable}&day=${day}`);
  }, [pathname, variable, day]);

  const setQuery = useCallback((next: { var?: Variable; day?: number }) => {
    if (next.var) setVariable(next.var);
    if (next.day) setDay(next.day);
  }, []);

  const { data, error, isLoading, mutate } = useApi<ForecastBundle>(`/api/blocks/${blockId}/panchayats/forecast`);

  // Keep the selected region in sync when this page is opened directly.
  useEffect(() => {
    const b = data?.meta?.block as { id: number; district_id?: number } | undefined;
    if (b && selection.blockId !== b.id) {
      setSelection({ stateId: selection.stateId, districtId: b.district_id ?? selection.districtId, blockId: b.id });
    }
  }, [data, selection, setSelection]);

  // Shared colour domain per variable (all GPs, all days, plus block values).
  const domain = useMemo(() => {
    if (!data) return { min: 0, max: 1 };
    const vals: number[] = [];
    data.features.forEach((f) => f.properties.days.forEach((d) => vals.push(d[variable] as number)));
    data.meta?.block_values.forEach((b) => b[variable] !== null && vals.push(b[variable] as number));
    return niceDomain(vals, variable);
  }, [data, variable]);

  // Insight chip for the current variable/day.
  const insight = useMemo(() => {
    if (!data) return null;
    const vals = data.features
      .map((f) => f.properties.days.find((d) => d.day === day)?.[variable] as number | null | undefined)
      .filter((v): v is number => v !== null && v !== undefined);
    if (!vals.length) return null;
    const bv = data.meta?.block_values.find((b) => b.day === day)?.[variable] ?? null;
    const unit = UNITS[variable];
    const n = (v: number) => String(Number(v.toFixed(variable === "rh" ? 0 : 1)));
    return t("insight", {
      variable: t(`varsLong.${variable}`),
      min: n(Math.min(...vals)),
      max: n(Math.max(...vals)),
      n: vals.length,
      block: bv === null ? "–" : n(bv),
      unit,
    });
  }, [data, day, variable, t]);

  // Full screen for projecting the hero map.
  const stageRef = useRef<HTMLDivElement>(null);
  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    const on = () => setFullscreen(document.fullscreenElement === stageRef.current);
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);
  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else stageRef.current?.requestFullscreen?.();
  };

  const isMobile = useIsMobile();
  const [mobileView, setMobileView] = useState<"block" | "panchayat">("panchayat");

  const { data: alertData } = useAlerts();
  const alertLevels = useMemo(() => {
    const out: Record<number, AlertLevel> = {};
    for (const a of alertData?.alerts ?? []) {
      if (a.day === day && (a.level === "orange" || a.level === "red")) out[a.panchayat_id] = a.level;
    }
    return out;
  }, [alertData, day]);

  const labels = useMemo(
    () => ({
      blockCaption: t("blockCaption"),
      gpCaption: t("gpCaption"),
      uniform: t("uniform"),
      range: t("range"),
      chance10: t("chance10"),
      vsBlock: t("vsBlock"),
      elevation: t("elevation"),
      confidence: { high: tc("high"), medium: tc("medium"), low: tc("low") } as Record<Confidence, string>,
      rainCategory: (mm: number) => tr(rainCategory(mm).key),
    }),
    [t, tc, tr],
  );

  const days = data?.meta?.days ?? [];
  const blockName = data ? localName(data.meta!.block, locale) : "";

  if (error) return <ErrorCard message={error.message} onRetry={() => mutate()} />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          {isLoading || !data ? (
            <Skeleton className="h-8 w-56" />
          ) : (
            <h1 className="text-2xl font-bold sm:text-3xl">{t("title", { block: blockName })}</h1>
          )}
          <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" asChild>
            <a href={`/api/blocks/${blockId}/bulletin.pdf`} target="_blank" rel="noopener">
              <FileDown /> {tb("download")}
            </a>
          </Button>
          <Button variant="secondary" onClick={toggleFullscreen} className="hidden md:inline-flex">
            <Maximize2 /> {t("fullscreen")}
          </Button>
        </div>
      </div>

      <div
        ref={stageRef}
        className={cn("flex flex-col gap-3", fullscreen && "h-screen overflow-hidden bg-background p-4")}
      >
        {/* Controls */}
        <Card className="flex flex-col gap-3 p-3 lg:flex-row lg:items-center lg:justify-between">
          <div role="tablist" aria-label={t("variable")} className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-0.5">
            {VARIABLES.map(({ key, icon: Icon }) => (
              <button
                key={key}
                role="tab"
                aria-selected={variable === key}
                onClick={() => setQuery({ var: key })}
                className={cn(
                  "inline-flex shrink-0 items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition-colors",
                  variable === key ? "bg-primary text-primary-foreground shadow-sm" : "text-foreground hover:bg-surface-2",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden /> {t(`vars.${key}`)}
              </button>
            ))}
          </div>

          <DaySelector
            days={days}
            value={day}
            onChange={(d) => setQuery({ day: d })}
            label={t("day")}
            formatDate={(iso) => format.dateTime(new Date(iso), { day: "numeric", month: "short" })}
            formatWeekday={(iso) => format.dateTime(new Date(iso), { weekday: "short" })}
          />

          {fullscreen && (
            <Button variant="secondary" size="sm" onClick={toggleFullscreen}>
              <Minimize2 /> {t("exitFullscreen")}
            </Button>
          )}
        </Card>

        {/* Mobile: single map with toggle */}
        {isMobile && (
          <div role="radiogroup" aria-label={t("viewToggle")} className="grid grid-cols-2 rounded-xl border bg-surface p-1 md:hidden">
            {(["block", "panchayat"] as const).map((v) => (
              <button
                key={v}
                role="radio"
                aria-checked={mobileView === v}
                onClick={() => setMobileView(v)}
                className={cn(
                  "rounded-lg py-2 text-sm font-semibold transition-colors",
                  mobileView === v ? "bg-primary text-primary-foreground" : "text-muted",
                )}
              >
                {v === "block" ? t("toggleBlock") : t("togglePanchayat")}
              </button>
            ))}
          </div>
        )}

        <div className={cn(fullscreen && "min-h-0 flex-1")}>
          {data ? (
            <SplitMap
              bundle={data}
              variable={variable}
              day={day}
              domain={domain}
              mobileView={isMobile ? mobileView : "panchayat"}
              projector={fullscreen}
              nameOf={(p) => localName(p, locale)}
              formatValue={formatValue}
              labels={labels}
              onOpenPanchayat={(id) => router.push(`/panchayat/${id}`)}
              alertLevels={alertLevels}
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              <Skeleton className="h-[60vh] md:h-[calc(100vh-21rem)] md:min-h-[440px]" />
              <Skeleton className="hidden h-[calc(100vh-21rem)] min-h-[440px] md:block" />
            </div>
          )}
        </div>

        {/* Legend + insight */}
        <Card className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:items-center">
          <div className="min-w-0">
            {variable === "rain" ? (
              <RainLegend
                labels={{
                  none: tr("none"),
                  very_light: tr("very_light"),
                  light: tr("light"),
                  moderate: tr("moderate"),
                  heavy: tr("heavy"),
                  very_heavy: tr("very_heavy"),
                }}
                note={t("rainNote")}
              />
            ) : (
              <ContinuousLegend
                tokens={SCALE_TOKENS[variable]}
                min={domain.min}
                max={domain.max}
                unit={UNITS[variable]}
                note={t("scaleNote")}
              />
            )}
          </div>
          <div className="flex flex-col gap-2">
            {insight ? (
              <p
                className="flex items-start gap-2 rounded-xl bg-accent/15 px-3.5 py-2.5 text-sm font-semibold text-foreground"
                aria-live="polite"
              >
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
                {insight}
              </p>
            ) : (
              <Skeleton className="h-10 w-full" />
            )}
            <p className="flex items-center gap-2 text-xs text-muted">
              <MousePointerClick className="h-3.5 w-3.5" aria-hidden /> {t("clickHint")}
            </p>
            <p className="text-xs text-muted">{t("boundaryNote")}</p>
          </div>
        </Card>
      </div>
    </div>
  );
}

function DaySelector({
  days,
  value,
  onChange,
  label,
  formatDate,
  formatWeekday,
}: {
  days: { day: number; date: string }[];
  value: number;
  onChange: (d: number) => void;
  label: string;
  formatDate: (iso: string) => string;
  formatWeekday: (iso: string) => string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: React.KeyboardEvent) => {
    const i = days.findIndex((d) => d.day === value);
    let next = i;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = Math.min(days.length - 1, i + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = Math.max(0, i - 1);
    else return;
    e.preventDefault();
    onChange(days[next].day);
    refs.current[next]?.focus();
  };
  if (!days.length) return <Skeleton className="h-12 w-full lg:w-96" />;
  const idx = Math.max(0, days.findIndex((d) => d.day === value));

  return (
    <div role="radiogroup" aria-label={label} onKeyDown={onKey} className="relative flex w-full items-stretch lg:w-auto">
      {/* track */}
      <div className="pointer-events-none absolute inset-x-6 top-[8px] h-0.5 rounded bg-border" aria-hidden />
      <div
        className="pointer-events-none absolute left-6 top-[8px] h-0.5 rounded bg-accent transition-all duration-300"
        style={{ width: `calc((100% - 3rem) * ${idx / Math.max(1, days.length - 1)})` }}
        aria-hidden
      />
      {days.map((d, i) => {
        const active = d.day === value;
        return (
          <button
            key={d.day}
            ref={(el) => {
              refs.current[i] = el;
            }}
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(d.day)}
            className="group relative flex min-w-[4.25rem] flex-1 flex-col items-center gap-1 px-1 lg:flex-none"
          >
            <span
              className={cn(
                "z-10 h-[18px] w-[18px] rounded-full border-2 transition-all",
                active
                  ? "scale-110 border-accent bg-accent shadow-[0_0_0_4px_rgb(var(--color-accent)/0.2)]"
                  : i < idx
                    ? "border-accent bg-surface"
                    : "border-border bg-surface group-hover:border-muted",
              )}
              aria-hidden
            />
            <span className={cn("text-xs font-bold", active ? "text-foreground" : "text-muted")}>
              {formatWeekday(d.date)}
            </span>
            <span className="text-[11px] text-muted">{formatDate(d.date)}</span>
          </button>
        );
      })}
    </div>
  );
}
