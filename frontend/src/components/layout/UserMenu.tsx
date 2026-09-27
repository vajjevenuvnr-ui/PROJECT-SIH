"use client";

import { LogOut, User } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DemoModeSwitch } from "@/components/layout/DemoModeSwitch";
import { useApi, useDemo, useRegion } from "@/components/providers/AppProviders";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { endDemoSession } from "@/lib/session";
import { useMe } from "@/lib/me";
import { localName } from "@/lib/names";
import { getSupabaseBrowser } from "@/lib/supabase/client";
import type { BlockSummary, Lang } from "@/lib/types";

export function UserMenu() {
  const t = useTranslations("topbar");
  const { demoSession } = useDemo();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    if (demoSession) return;
    getSupabaseBrowser()
      ?.auth.getUser()
      .then(({ data }) => setEmail(data.user?.email ?? null));
  }, [demoSession]);

  const locale = useLocale() as Lang;
  const { selection } = useRegion();
  const summary = useApi<BlockSummary>(selection.blockId ? `/api/blocks/${selection.blockId}/summary` : null);
  const block = summary.data ? localName(summary.data.block, locale) : null;
  const me = useMe();
  const name = demoSession ? t("demoName") : (me?.name ?? email?.split("@")[0] ?? t("officer"));
  const role = me?.role === "admin" ? t("admin") : block ? t("roleAt", { block }) : t("role");
  const initials = demoSession ? "L" : (email?.[0] ?? "O").toUpperCase();

  const signOut = async () => {
    try {
      await getSupabaseBrowser()?.auth.signOut();
    } catch {}
    endDemoSession();
    router.replace("/login");
    router.refresh();
  };

  return (
    <DropdownMenu>
      <span className="hidden text-right text-xs leading-tight lg:block">
        <span className="block font-semibold">{name}</span>
        <span className="block text-muted">{role}</span>
      </span>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t("account")}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground transition hover:opacity-90"
        >
          {initials}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="flex items-center gap-2 text-foreground">
          <User className="h-4 w-4 text-muted" /> <span className="truncate">
            {name} · {role}
          </span>
        </DropdownMenuLabel>
        <div className="px-3 py-2 md:hidden">
          <DemoModeSwitch />
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={signOut}>
          <LogOut /> {t("signOut")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
