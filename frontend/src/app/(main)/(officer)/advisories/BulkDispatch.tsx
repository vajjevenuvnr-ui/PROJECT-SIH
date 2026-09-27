"use client";

import { CheckCircle2, Loader2, Send, Wand2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { ConfidencePill } from "@/components/data/ConfidencePill";
import { useDemo, useRegion } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { localName } from "@/lib/names";
import type { Advisory, Confidence, Lang } from "@/lib/types";

type Draft = {
  advisory: Advisory;
  profile: { crop: string; stage_name: Record<Lang, string> };
  panchayat: { id: number; name: string; name_te?: string | null; name_hi?: string | null };
  confidence: Confidence;
  warnings: number;
};

/** One click drafts advisories for every panchayat from its crop profile; officer ticks and sends. */
export function BulkDispatch() {
  const t = useTranslations("bulk");
  const tc = useTranslations("confidence");
  const locale = useLocale() as Lang;
  const { demo } = useDemo();
  const { selection } = useRegion();
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState<"gen" | "send" | null>(null);
  const [result, setResult] = useState<{ sent: number; farmers: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!selection.blockId) return null;

  const generate = async () => {
    setBusy("gen");
    setError(null);
    setResult(null);
    try {
      const d = await api<Draft[]>("/api/advisory/generate-bulk", {
        demo,
        method: "POST",
        body: { block_id: selection.blockId },
      });
      setDrafts(d);
      // Pre-select panchayats that actually have something to do.
      setPicked(new Set(d.filter((x) => x.advisory.items.length > 0).map((x) => x.advisory.id)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const send = async () => {
    setBusy("send");
    setError(null);
    try {
      const r = await api<{ sent: number; farmers: number }>("/api/advisory/send-bulk", {
        demo,
        method: "POST",
        body: { advisory_ids: Array.from(picked), channel: "sms", language: locale },
      });
      setResult(r);
      setPicked(new Set());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const toggle = (id: number) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold sm:text-3xl">{t("title")}</h1>
          <p className="mt-1 text-muted">{t("subtitle")}</p>
        </div>
        <Button onClick={generate} disabled={busy !== null}>
          {busy === "gen" ? <Loader2 className="animate-spin" /> : <Wand2 />}
          {busy === "gen" ? t("generating") : t("generate")}
        </Button>
      </div>

      {error && <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}
      {result && (
        <p className="flex items-center gap-2 rounded-lg bg-success/10 px-3 py-2 text-sm font-semibold text-success">
          <CheckCircle2 className="h-4 w-4" aria-hidden /> {t("sent", { n: result.sent, farmers: result.farmers })}
        </p>
      )}

      {drafts.length === 0 ? (
        <Card className="p-6 text-center text-sm text-muted">{t("empty")}</Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="ghost" onClick={() => setPicked(new Set(drafts.map((d) => d.advisory.id)))}>
              {t("all")}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPicked(new Set())}>
              {t("none")}
            </Button>
            <Button className="ml-auto" onClick={send} disabled={busy !== null || picked.size === 0}>
              {busy === "send" ? <Loader2 className="animate-spin" /> : <Send />}
              {busy === "send" ? t("sending") : t("send", { n: picked.size })}
            </Button>
          </div>
          <Card className="divide-y">
            {drafts.map((d) => {
              const id = d.advisory.id;
              const top = d.advisory.items[0];
              return (
                <label key={id} className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-surface-2">
                  <input
                    type="checkbox"
                    checked={picked.has(id)}
                    onChange={() => toggle(id)}
                    aria-label={`${t("select")} ${localName(d.panchayat, locale)}`}
                    className="h-4 w-4 accent-primary"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{localName(d.panchayat, locale)}</p>
                    <p className="truncate text-xs text-muted">
                      {d.profile.crop} · {d.profile.stage_name[locale]}
                      {d.warnings > 0 && ` · ${t("warnings", { n: d.warnings })}`}
                    </p>
                    <p className="truncate text-sm">{top ? top.title[locale] : t("noAction")}</p>
                  </div>
                  <ConfidencePill level={d.confidence} label={tc(d.confidence)} className="hidden sm:inline-flex" />
                  <Link
                    href={`/panchayat/${d.panchayat.id}/advisory`}
                    className="text-sm font-semibold text-primary hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {t("open")}
                  </Link>
                </label>
              );
            })}
          </Card>
        </>
      )}
    </div>
  );
}
