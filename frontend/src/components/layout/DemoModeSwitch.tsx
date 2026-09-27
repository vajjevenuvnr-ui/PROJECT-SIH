"use client";

import { useTranslations } from "next-intl";

import { useDemo } from "@/components/providers/AppProviders";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

export function DemoModeSwitch({ className }: { className?: string }) {
  const t = useTranslations("topbar");
  const { demo, demoSession, setDemo } = useDemo();
  return (
    <label
      className={cn(
        "inline-flex cursor-pointer items-center gap-2 text-xs font-medium",
        demoSession && "cursor-not-allowed",
        className,
      )}
      title={demoSession ? t("demoLocked") : t("demo")}
    >
      <Switch checked={demo} disabled={demoSession} onCheckedChange={setDemo} aria-label={t("demo")} />
      <span className="text-muted">{t("demo")}</span>
    </label>
  );
}

export function DemoBadge() {
  const t = useTranslations("topbar");
  const { demo } = useDemo();
  if (!demo) return null;
  return (
    <span className="inline-flex items-center rounded-full bg-accent px-2 py-0.5 text-[11px] font-bold tracking-wider text-accent-foreground">
      {t("demoBadge")}
    </span>
  );
}
