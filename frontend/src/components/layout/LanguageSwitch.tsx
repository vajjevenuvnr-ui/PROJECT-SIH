"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { LOCALE_COOKIE, localeLabels, localeNames, locales, type Locale } from "@/i18n/config";
import { setClientCookie } from "@/lib/session";
import { cn } from "@/lib/utils";

export function LanguageSwitch({ className }: { className?: string }) {
  const t = useTranslations("topbar");
  const current = useLocale() as Locale;
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const choose = (l: Locale) => {
    if (l === current) return;
    setClientCookie(LOCALE_COOKIE, l);
    startTransition(() => router.refresh());
  };

  return (
    <div
      role="radiogroup"
      aria-label={t("language")}
      className={cn("inline-flex h-9 items-center rounded-full border bg-surface p-0.5", pending && "opacity-70", className)}
    >
      {locales.map((l) => (
        <button
          key={l}
          type="button"
          role="radio"
          aria-checked={l === current}
          title={localeNames[l]}
          onClick={() => choose(l)}
          className={cn(
            "h-full min-w-9 rounded-full px-2.5 text-xs font-semibold transition-colors",
            l === current ? "bg-primary text-primary-foreground" : "text-muted hover:text-foreground",
          )}
        >
          {localeLabels[l]}
        </button>
      ))}
    </div>
  );
}
