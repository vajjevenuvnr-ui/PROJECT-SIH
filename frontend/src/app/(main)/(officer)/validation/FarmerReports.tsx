"use client";

import { MessageSquareHeart } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { useApi, useRegion } from "@/components/providers/AppProviders";
import { Card } from "@/components/ui/card";
import { localName } from "@/lib/names";
import type { Lang } from "@/lib/types";
import { cn } from "@/lib/utils";

type Summary = {
  reports: number;
  agreement: number | null;
  judged: number;
  rows: {
    panchayat_id: number;
    panchayat: { id: number; name: string; name_te?: string | null; name_hi?: string | null };
    date: string;
    yes: number;
    no: number;
    forecast_rain_mm: number | null;
    agree: boolean | null;
  }[];
};

/** Crowdsourced "Did it rain today?" answers compared with the forecast for that panchayat and day. */
export function FarmerReports() {
  const t = useTranslations("farmerReports");
  const locale = useLocale() as Lang;
  const { selection } = useRegion();
  const { data } = useApi<Summary>(selection.blockId ? `/api/feedback/summary?block_id=${selection.blockId}` : null);
  if (!data) return null;
  return (
    <Card className="mx-auto w-full max-w-6xl p-5">
      <h2 className="flex items-center gap-2 text-lg font-bold">
        <MessageSquareHeart className="h-5 w-5 text-primary" aria-hidden /> {t("title")}
      </h2>
      <p className="text-sm text-muted">{t("subtitle")}</p>
      {data.rows.length === 0 ? (
        <p className="mt-3 text-sm text-muted">{t("none")}</p>
      ) : (
        <>
          {data.agreement != null && (
            <p className="mt-3 text-sm font-semibold">
              {t("agreement", { p: Math.round(data.agreement * 100), n: data.judged })}
            </p>
          )}
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th className="py-1 pr-3" />
                  <th className="py-1 pr-3" />
                  <th className="py-1 pr-3">{t("yes")}</th>
                  <th className="py-1 pr-3">{t("no")}</th>
                  <th className="py-1 pr-3">{t("forecast")}</th>
                  <th className="py-1">{t("match")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.rows.map((r) => (
                  <tr key={`${r.panchayat_id}-${r.date}`}>
                    <td className="py-1.5 pr-3 font-medium">{localName(r.panchayat, locale)}</td>
                    <td className="py-1.5 pr-3 text-muted">{r.date}</td>
                    <td className="py-1.5 pr-3">{r.yes}</td>
                    <td className="py-1.5 pr-3">{r.no}</td>
                    <td className="py-1.5 pr-3">{r.forecast_rain_mm == null ? "–" : `${r.forecast_rain_mm} mm`}</td>
                    <td
                      className={cn(
                        "py-1.5 font-semibold",
                        r.agree === true && "text-success",
                        r.agree === false && "text-danger",
                        r.agree == null && "text-muted",
                      )}
                    >
                      {r.agree === true ? t("agree") : r.agree === false ? t("disagree") : t("tie")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
