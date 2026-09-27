"use client";

import { CloudOff, Database } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import Link from "next/link";

import { Logo } from "@/components/brand/Logo";
import { DemoBadge, DemoModeSwitch } from "@/components/layout/DemoModeSwitch";
import { LanguageSwitch } from "@/components/layout/LanguageSwitch";
import { UserMenu } from "@/components/layout/UserMenu";
import { useApi, useDataStatus, useRegion } from "@/components/providers/AppProviders";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { AlertBell } from "@/components/alerts/AlertCenter";
import type { BlockSummary } from "@/lib/types";

export function TopBar() {
  const t = useTranslations("topbar");
  const format = useFormatter();
  const { selection } = useRegion();
  const { stale } = useDataStatus();
  const { data } = useApi<BlockSummary>(selection.blockId ? `/api/blocks/${selection.blockId}/summary` : null);
  const run = data?.run;

  return (
    <header className="sticky top-0 z-[1000] border-b bg-surface/90 backdrop-blur supports-[backdrop-filter]:bg-surface/75">
      <div className="flex h-14 items-center gap-3 px-3 sm:px-4">
        <Link href="/" className="flex shrink-0 items-center" aria-label="Kshetra home">
          <Logo size="sm" priority />
        </Link>
        <DemoBadge />

        {run && (
          <div className="hidden min-w-0 items-center gap-2 lg:flex">
            <span className="whitespace-nowrap text-sm text-muted">
              {t("issued")}:{" "}
              <span className="font-semibold text-foreground">
                {format.dateTime(new Date(run.issued_at), {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                  hour12: false,
                })}
              </span>
            </span>
            <span
              className="inline-flex max-w-72 items-center gap-1.5 truncate rounded-full border bg-surface-2 px-2.5 py-0.5 text-xs text-muted"
              title={run.source_label}
            >
              <Database className="h-3 w-3 shrink-0" aria-hidden />
              <span className="truncate">{run.source_label}</span>
            </span>
          </div>
        )}
        {stale && (
          <span
            className="inline-flex items-center gap-1.5 rounded-full bg-accent/20 px-2.5 py-0.5 text-xs font-semibold text-foreground"
            title={t("cachedHint")}
          >
            <CloudOff className="h-3.5 w-3.5 text-warning" aria-hidden /> {t("cached")}
          </span>
        )}

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <DemoModeSwitch className="hidden md:inline-flex" />
          <LanguageSwitch />
          <AlertBell />
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
