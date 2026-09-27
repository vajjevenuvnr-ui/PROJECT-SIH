"use client";

import { AlertTriangle, ArrowRight, CheckCircle2, CircleAlert, Clock, MapPinned, Users } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect } from "react";

import { LEVEL_STYLE } from "@/components/alerts/AlertCenter";
import { useApi, useRegion } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Combobox, type ComboOption } from "@/components/ui/combobox";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import { localName } from "@/lib/names";
import type { BlockSummary, DistrictFeatureProps, FeatureCollection, Lang, Region } from "@/lib/types";
import { cn } from "@/lib/utils";

const DistrictMiniMap = dynamic(() => import("@/components/map/DistrictMiniMap"), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full" />,
});

function useOptions(rows: Region[] | undefined, locale: string): ComboOption[] {
  return (rows ?? []).map((r) => ({
    value: String(r.id),
    label: localName(r, locale),
    keywords: [r.name, r.name_te ?? "", r.name_hi ?? ""],
    hint: locale !== "en" ? r.name : undefined,
  }));
}

function StatCard({
  icon: Icon,
  label,
  children,
  tone = "default",
  loading,
}: {
  icon: React.ElementType;
  label: string;
  children: React.ReactNode;
  tone?: "default" | "warning" | "success" | "danger";
  loading?: boolean;
}) {
  const toneCls = {
    default: "bg-primary/10 text-primary",
    warning: "bg-accent/20 text-warning",
    success: "bg-success/15 text-success",
    danger: "bg-danger/15 text-danger",
  }[tone];
  return (
    <Card className="flex items-center gap-4 p-5">
      <span className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl", toneCls)}>
        <Icon className="h-6 w-6" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-sm text-muted">{label}</p>
        {loading ? <Skeleton className="mt-1 h-7 w-24" /> : <div className="text-2xl font-bold leading-tight">{children}</div>}
      </div>
    </Card>
  );
}

export function HomeView() {
  const t = useTranslations("home");
  const ta = useTranslations("alerts");
  const locale = useLocale();
  const format = useFormatter();
  const { selection, setSelection, ready } = useRegion();
  const { stateId, districtId, blockId } = selection;

  const states = useApi<Region[]>("/api/regions/states");
  const districts = useApi<Region[]>(stateId ? `/api/regions/districts?state=${stateId}` : null);
  const blocks = useApi<Region[]>(districtId ? `/api/regions/blocks?district=${districtId}` : null);
  const summary = useApi<BlockSummary>(blockId ? `/api/blocks/${blockId}/summary` : null);
  const districtGeo = useApi<FeatureCollection<DistrictFeatureProps>>(
    districtId ? `/api/regions/districts/${districtId}/geojson` : null,
  );

  const stateOpts = useOptions(states.data, locale);
  const districtOpts = useOptions(districts.data, locale);
  const blockOpts = useOptions(blocks.data, locale).map((o) => {
    const n = blocks.data?.find((b) => String(b.id) === o.value)?.panchayat_count;
    return n === 0 ? { ...o, disabled: true, hint: t("noData") } : n ? { ...o, hint: t("pilot", { n }) } : o;
  });
  const covered = (id: number) => (blocks.data?.find((b) => b.id === id)?.panchayat_count ?? 1) > 0;

  // A saved block with no data (e.g. from before the pilot limits): move to the first covered block.
  useEffect(() => {
    if (!blockId || !blocks.data?.length) return;
    const cur = blocks.data.find((b) => b.id === blockId);
    const firstCovered = blocks.data.find((b) => (b.panchayat_count ?? 0) > 0);
    if (cur && cur.panchayat_count === 0 && firstCovered) setSelection({ stateId, districtId, blockId: firstCovered.id });
  }, [blockId, blocks.data, stateId, districtId, setSelection]);

  // Auto-pick when there is only one choice (e.g. one pilot state).
  useEffect(() => {
    if (!ready) return;
    if (!stateId && states.data?.length === 1) setSelection({ stateId: states.data[0].id, districtId: null, blockId: null });
    else if (stateId && !districtId && districts.data?.length === 1)
      setSelection({ stateId, districtId: districts.data[0].id, blockId: null });
  }, [ready, stateId, districtId, states.data, districts.data, setSelection]);

  const s = summary.data;
  const run = s?.run;
  const runDone = run ? new Date(new Date(run.issued_at).getTime() + (run.duration_s ?? 0) * 1000) : null;
  const time = runDone ? format.dateTime(runDone, { hour: "2-digit", minute: "2-digit", hour12: false }) : "";
  const loadErr = states.error || districts.error || blocks.error || summary.error;
  const retryAll = () => {
    states.mutate();
    districts.mutate();
    blocks.mutate();
    summary.mutate();
  };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">{t("title")}</h1>
        <p className="mt-1 text-muted">{t("subtitle")}</p>
        <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
          {t("audience")}
        </p>
      </div>

      {/* Cascading selects */}
      <Card className="p-4 sm:p-5">
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            { id: "sel-state", label: t("state"), value: stateId, opts: stateOpts, loading: states.isLoading,
              onChange: (v: string) => setSelection({ stateId: Number(v), districtId: null, blockId: null }) },
            { id: "sel-district", label: t("district"), value: districtId, opts: districtOpts, loading: districts.isLoading,
              disabled: !stateId,
              onChange: (v: string) => setSelection({ stateId, districtId: Number(v), blockId: null }) },
            { id: "sel-block", label: t("block"), value: blockId, opts: blockOpts, loading: blocks.isLoading,
              disabled: !districtId,
              onChange: (v: string) => setSelection({ stateId, districtId, blockId: Number(v) }) },
          ].map((f) => (
            <div key={f.id} className="flex flex-col gap-1.5">
              <label htmlFor={f.id} className="text-sm font-medium">
                {f.label}
              </label>
              <Combobox
                id={f.id}
                value={f.value ? String(f.value) : null}
                onChange={f.onChange}
                options={f.opts}
                loading={f.loading}
                disabled={f.disabled}
                placeholder={t("select")}
                searchPlaceholder={t("search")}
                emptyText={t("noResults")}
              />
            </div>
          ))}
        </div>
      </Card>

      {loadErr && <ErrorCard message={loadErr.message} onRetry={retryAll} />}

      {!blockId ? (
        <Card className="flex items-center gap-3 p-5 text-muted">
          <MapPinned className="h-5 w-5 text-primary" aria-hidden /> {t("pickBlock")}
        </Card>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard icon={Users} label={t("panchayats")} loading={!s}>
              {s?.panchayat_count} <span className="text-base font-semibold text-muted">{t("gpsUnit")}</span>
            </StatCard>
            <StatCard
              icon={AlertTriangle}
              label={t("alerts")}
              tone={s && s.active_alerts > 0 ? "warning" : "success"}
              loading={!s}
            >
              {s ? t("alertsCount", { count: s.active_alerts }) : null}
            </StatCard>
            <StatCard
              icon={run?.status === "failed" ? CircleAlert : run?.status === "stale" ? Clock : CheckCircle2}
              label={t("modelRun")}
              tone={run?.status === "failed" ? "danger" : run?.status === "stale" ? "warning" : "success"}
              loading={!s}
            >
              {run?.status === "failed"
                ? t("runFailed")
                : run?.status === "stale"
                  ? t("runStale", { time })
                  : t("runOk", { time })}
              {run && <p className="truncate text-xs font-normal text-muted">{run.source_label}</p>}
            </StatCard>
          </div>

          {/* Map + alerts */}
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="overflow-hidden lg:col-span-2">
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>{t("districtMap")}</CardTitle>
                <span className="flex items-center gap-2 text-xs text-muted">
                  <span className="h-3 w-3 rounded-sm bg-primary/60" aria-hidden /> {t("mapLegendSelected")}
                </span>
              </CardHeader>
              <CardContent>
                <div className="h-72 sm:h-80">
                  {districtGeo.data ? (
                    <DistrictMiniMap
                      data={districtGeo.data}
                      selectedBlockId={blockId}
                      onSelectBlock={(id) => covered(id) && setSelection({ stateId, districtId, blockId: id })}
                      nameOf={(p) => localName(p, locale)}
                    />
                  ) : (
                    <Skeleton className="h-full w-full" />
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("alerts")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {!s && <Skeleton className="h-20 w-full" />}
                {s && s.alerts.length === 0 && !s.warnings?.length && <p className="text-sm text-muted">{ta("none")}</p>}
                {s?.warnings?.slice(0, 3).map((w) => (
                  <div key={w.id} className={cn("rounded-xl p-3", LEVEL_STYLE[w.level])}>
                    <div className="flex items-center justify-between gap-2 text-xs font-bold">
                      <span>{w.title[locale as Lang]}</span>
                      <span>{format.dateTime(new Date(w.date), { weekday: "short", day: "numeric", month: "short" })}</span>
                    </div>
                    <p className="mt-1 font-semibold">
                      {localName(w.panchayat, locale)} · {w.value} {w.unit}
                    </p>
                  </div>
                ))}
                {s?.alerts.slice(0, 4).map((a, i) => (
                  <div
                    key={i}
                    className={cn(
                      "rounded-xl border-l-4 bg-surface-2 p-3",
                      a.severity === "warning" ? "border-danger" : "border-accent",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className={cn("font-bold uppercase", a.severity === "warning" ? "text-danger" : "text-warning")}>
                        {ta(a.severity)}
                      </span>
                      <span className="text-muted">
                        {format.dateTime(new Date(a.date), { weekday: "short", day: "numeric", month: "short" })}
                      </span>
                    </div>
                    <p className="mt-1 font-semibold">{ta(`${a.type}.${a.severity}`)}</p>
                    <p className="text-sm text-muted">{a.panchayat_name}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <div className="flex justify-end">
            <Button asChild size="lg" className="w-full sm:w-auto">
              <Link href={`/block/${blockId}`}>
                {t("openDashboard")} <ArrowRight />
              </Link>
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
