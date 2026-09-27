"use client";

import { ArrowRight, CheckCircle2 } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import Link from "next/link";

import { useApi } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { localeNames } from "@/i18n/config";
import type { ShareLogEntry } from "@/lib/types";

/** Share nav item: recent sends, each linking back to its share screen. */
export function ShareIndex() {
  const t = useTranslations("share");
  const format = useFormatter();
  const { data } = useApi<ShareLogEntry[]>("/api/share/log");

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">{t("indexTitle")}</h1>
        <p className="mt-1 text-muted">{t("indexSubtitle")}</p>
      </div>
      <Card className="divide-y">
        {!data && (
          <div className="p-4">
            <Skeleton className="h-6 w-full" />
          </div>
        )}
        {data?.length === 0 && (
          <div className="flex flex-col items-start gap-3 p-5">
            <p className="text-muted">{t("logEmpty")}</p>
            <Button asChild variant="secondary">
              <Link href="/advisories">
                {t("goAdvisories")} <ArrowRight />
              </Link>
            </Button>
          </div>
        )}
        {data?.map((r) => (
          <Link key={r.id} href={`/share/${r.advisory_id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2">
            <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden />
            <div className="min-w-0 flex-1 text-sm">
              <p className="font-semibold">
                {t(r.channel)} · {localeNames[r.language]} · {r.recipients}
              </p>
              <p className="text-xs text-muted">
                {format.dateTime(new Date(r.sent_at), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false })} ·{" "}
                {t("delivered")}
              </p>
            </div>
            <span className="text-sm font-semibold text-primary">{t("open")}</span>
          </Link>
        ))}
      </Card>
    </div>
  );
}
