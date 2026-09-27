"use client";

import { ArrowRight, CloudRain } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";

import { ConfidencePill } from "@/components/data/ConfidencePill";
import { useApi, useRegion } from "@/components/providers/AppProviders";
import { Card } from "@/components/ui/card";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import { localName } from "@/lib/names";
import type { Confidence, ForecastBundle } from "@/lib/types";
import { num } from "@/lib/weather";

const RANK: Record<Confidence, number> = { high: 0, medium: 1, low: 2 };

/** Panchayats of the selected block, wettest first, each linking to its advisory generator. */
export function AdvisoriesList() {
  const t = useTranslations("advisories");
  const tc = useTranslations("confidence");
  const locale = useLocale();
  const { selection } = useRegion();
  const { data, error, mutate } = useApi<ForecastBundle>(
    selection.blockId ? `/api/blocks/${selection.blockId}/panchayats/forecast` : null,
  );

  if (!selection.blockId) return <p className="text-muted">{t("noBlock")}</p>;
  if (error) return <ErrorCard message={error.message} onRetry={() => mutate()} />;

  const rows = (data?.features ?? [])
    .map((f) => {
      const d3 = f.properties.days.slice(0, 3);
      return {
        p: f.properties,
        maxRain: Math.max(...d3.map((d) => d.rain)),
        conf: d3.reduce<Confidence>((w, d) => (RANK[d.confidence] > RANK[w] ? d.confidence : w), "high"),
      };
    })
    .sort((a, b) => b.maxRain - a.maxRain);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">{t("title")}</h1>
        <p className="mt-1 text-muted">
          {t("subtitle", { block: data?.meta ? localName(data.meta.block, locale) : "…" })}
        </p>
      </div>
      <Card className="divide-y">
        {!data &&
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="p-4">
              <Skeleton className="h-6 w-full" />
            </div>
          ))}
        {rows.map(({ p, maxRain, conf }) => (
          <Link
            key={p.id}
            href={`/panchayat/${p.id}/advisory`}
            className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-2"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{localName(p, locale)}</p>
              <p className="flex items-center gap-1 text-xs text-muted">
                <CloudRain className="h-3.5 w-3.5" aria-hidden /> {t("maxRain")}: {num(maxRain)} mm
              </p>
            </div>
            <ConfidencePill level={conf} label={tc(conf)} className="hidden sm:inline-flex" />
            <span className="inline-flex items-center gap-1 text-sm font-semibold text-primary">
              {t("open")} <ArrowRight className="h-4 w-4" aria-hidden />
            </span>
          </Link>
        ))}
      </Card>
    </div>
  );
}
