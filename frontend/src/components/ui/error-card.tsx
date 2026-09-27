"use client";

import { AlertTriangle, RotateCw } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ErrorCard({
  message,
  onRetry,
  className,
}: {
  message?: string;
  onRetry?: () => void;
  className?: string;
}) {
  const t = useTranslations("common");
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center gap-3 rounded-card border border-danger/30 bg-danger/5 px-6 py-8 text-center",
        className,
      )}
    >
      <AlertTriangle className="h-6 w-6 text-danger" aria-hidden />
      <div>
        <p className="font-semibold">{t("somethingWrong")}</p>
        <p className="mt-1 text-sm text-muted">{message ?? t("couldNotLoad")}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RotateCw /> {t("retry")}
        </Button>
      )}
    </div>
  );
}
