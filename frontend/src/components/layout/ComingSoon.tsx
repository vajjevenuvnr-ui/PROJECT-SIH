import { Construction } from "lucide-react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";

/** Placeholder for screens built in later phases, so navigation never dead-ends. */
export async function ComingSoon({ title, phase }: { title: string; phase: string }) {
  const t = await getTranslations("common");
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-4 rounded-card border border-dashed bg-surface px-6 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-accent/20">
        <Construction className="h-6 w-6 text-warning" aria-hidden />
      </span>
      <div>
        <h1 className="text-xl font-bold">{title}</h1>
        <p className="mt-1 text-sm text-muted">
          {t("comingSoon", { phase })} · {t("comingSoonBody")}
        </p>
      </div>
      <Button asChild variant="secondary">
        <Link href="/">{t("backHome")}</Link>
      </Button>
    </div>
  );
}
