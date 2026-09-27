import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Logo } from "@/components/brand/Logo";
import { LanguageSwitch } from "@/components/layout/LanguageSwitch";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

import { SetPasswordForm } from "./SetPasswordForm";

export const metadata: Metadata = { title: "Set password" };

/** Landing page for the officer invite link: the officer chooses a password. */
export default async function SetPasswordPage() {
  const t = await getTranslations("setPassword");
  return (
    <main className="flex min-h-screen flex-col bg-surface">
      <div className="flex items-center justify-between p-4">
        <Logo size="md" />
        <div className="flex items-center gap-2">
          <LanguageSwitch />
          <ThemeToggle />
        </div>
      </div>
      <div className="flex flex-1 items-center justify-center px-4 pb-12">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="mt-1.5 text-sm text-muted">{t("subtitle")}</p>
          <SetPasswordForm />
        </div>
      </div>
    </main>
  );
}
