"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS } from "@/components/layout/nav";
import { useRegion } from "@/components/providers/AppProviders";
import { useMe } from "@/lib/me";
import { cn } from "@/lib/utils";

function useNav() {
  const pathname = usePathname();
  const { selection } = useRegion();
  const me = useMe();
  return NAV_ITEMS.filter((item) => !item.adminOnly || me?.role === "admin").map((item) => ({
    ...item,
    url: item.href(selection.blockId),
    active: item.match(pathname),
  }));
}

/** Desktop: 240 px left sidebar. */
export function Sidebar() {
  const t = useTranslations("nav");
  const items = useNav();
  return (
    <nav
      aria-label={t("main")}
      className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-60 shrink-0 flex-col gap-1 border-r bg-surface px-3 py-4 md:flex"
    >
      {items.map(({ key, icon: Icon, url, active }) => {
        const cls = cn(
          "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
          active ? "bg-primary text-primary-foreground shadow-sm" : "text-foreground hover:bg-surface-2",
          !url && "cursor-not-allowed opacity-50 hover:bg-transparent",
        );
        return url ? (
          <Link key={key} href={url} className={cls} aria-current={active ? "page" : undefined}>
            <Icon className="h-[18px] w-[18px]" aria-hidden /> {t(key)}
          </Link>
        ) : (
          <span key={key} className={cls} title={t("selectBlockFirst")} aria-disabled>
            <Icon className="h-[18px] w-[18px]" aria-hidden /> {t(key)}
          </span>
        );
      })}
    </nav>
  );
}

/** Mobile (<768 px): bottom tab bar. */
export function BottomNav() {
  const t = useTranslations("nav");
  const items = useNav().filter((i) => !i.adminOnly);
  return (
    <nav
      aria-label={t("main")}
      className="fixed inset-x-0 bottom-0 z-[1000] grid grid-cols-6 border-t bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {items.map(({ key, icon: Icon, url, active }) => {
        const cls = cn(
          "flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium leading-tight",
          active ? "text-primary" : "text-muted",
          !url && "opacity-40",
        );
        const inner = (
          <>
            <span className={cn("flex h-7 w-12 items-center justify-center rounded-full", active && "bg-primary/15")}>
              <Icon className="h-5 w-5" aria-hidden />
            </span>
            <span className="max-w-full truncate px-1">{t(key)}</span>
          </>
        );
        return url ? (
          <Link key={key} href={url} className={cls} aria-current={active ? "page" : undefined}>
            {inner}
          </Link>
        ) : (
          <span key={key} className={cls} aria-disabled>
            {inner}
          </span>
        );
      })}
    </nav>
  );
}
