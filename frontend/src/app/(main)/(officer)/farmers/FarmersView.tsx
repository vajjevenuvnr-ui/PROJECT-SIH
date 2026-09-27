"use client";

import { Download, Loader2, ShieldCheck, Trash2, Upload, UserPlus, Users } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { useApi, useDemo, useRegion } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { localName } from "@/lib/names";
import type { BlockSummary, Lang } from "@/lib/types";

type Farmer = {
  id: number;
  panchayat_id: number;
  panchayat: { id: number; name: string; name_te?: string | null; name_hi?: string | null };
  name: string | null;
  mobile_masked: string;
  crop: string | null;
  language: Lang;
  source: "upload" | "self";
};
type FarmersResponse = {
  total: number;
  self_registered: number;
  panchayats_covered: number;
  panchayats: number;
  farmers: Farmer[];
};
type UploadResult = {
  added: number;
  updated: number;
  error_count: number;
  errors: { row: number; reason: "invalid_mobile" | "unknown_panchayat"; value?: string }[];
};

const LANG_LABEL: Record<Lang, string> = { te: "తెలుగు", hi: "हिंदी", en: "English" };

/** Officer's farmer contact list: import CSV / Excel, see masked numbers, remove. */
export function FarmersView() {
  const t = useTranslations("farmers");
  const locale = useLocale() as Lang;
  const { demo } = useDemo();
  const { selection } = useRegion();
  const blockId = selection.blockId;
  const summary = useApi<BlockSummary>(blockId ? `/api/blocks/${blockId}/summary` : null);
  const { data, error, mutate } = useApi<FarmersResponse>(blockId ? `/api/farmers?block_id=${blockId}` : null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [q, setQ] = useState("");

  if (!blockId) return <p className="text-muted">{t("noBlock")}</p>;
  if (error) return <ErrorCard message={error.message} onRetry={() => mutate()} />;

  const upload = async (file: File) => {
    setBusy(true);
    setResult(null);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await api<UploadResult>(`/api/farmers/upload?block_id=${blockId}`, { demo, method: "POST", body: form });
      setResult(r);
      await mutate();
    } catch (e) {
      setUploadError((e as Error).message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const remove = async (id: number) => {
    await api(`/api/farmers/${id}`, { demo, method: "DELETE" }).catch(() => null);
    await mutate();
  };

  const needle = q.trim().toLowerCase();
  const rows = (data?.farmers ?? []).filter(
    (f) =>
      !needle ||
      (f.name ?? "").toLowerCase().includes(needle) ||
      localName(f.panchayat, locale).toLowerCase().includes(needle),
  );

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">{t("title")}</h1>
        <p className="mt-1 text-muted">
          {t("subtitle", { block: summary.data ? localName(summary.data.block, locale) : "…" })}
        </p>
      </div>

      <Card className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
          <Button onClick={() => fileRef.current?.click()} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <Upload />} {busy ? t("uploading") : t("upload")}
          </Button>
          <Button variant="secondary" asChild>
            <a href="/api/farmers/template.csv" download>
              <Download /> {t("template")}
            </a>
          </Button>
        </div>
        <p className="text-xs text-muted">{t("columns")}</p>
        {uploadError && <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{uploadError}</p>}
        {result && (
          <div className="rounded-lg bg-success/10 px-3 py-2 text-sm">
            <p className="font-semibold text-success">
              {t("result", { added: result.added, updated: result.updated, errors: result.error_count })}
            </p>
            {result.errors.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-xs text-muted">
                {result.errors.slice(0, 8).map((e) => (
                  <li key={e.row}>
                    {e.reason === "invalid_mobile"
                      ? t("errInvalid_mobile", { row: e.row })
                      : t("errUnknown_panchayat", { row: e.row, value: e.value ?? "" })}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Card>

      <div className="grid grid-cols-3 gap-3">
        {[
          { icon: Users, label: t("total"), value: data?.total },
          { icon: UserPlus, label: t("self"), value: data?.self_registered },
          { icon: ShieldCheck, label: t("covered"), value: data ? `${data.panchayats_covered} / ${data.panchayats}` : undefined },
        ].map(({ icon: Icon, label, value }) => (
          <Card key={label} className="p-4">
            <p className="flex items-center gap-1.5 text-xs text-muted">
              <Icon className="h-3.5 w-3.5" aria-hidden /> {label}
            </p>
            <p className="mt-1 text-2xl font-bold">{value ?? "–"}</p>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b p-3">
          <p className="flex items-center gap-1.5 text-xs text-muted">
            <ShieldCheck className="h-3.5 w-3.5 text-success" aria-hidden /> {t("privacy")}
          </p>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("search")}
            aria-label={t("search")}
            className="h-9 w-full rounded-md border bg-surface px-3 text-sm sm:w-64"
          />
        </div>
        {!data ? (
          <div className="p-4">
            <Skeleton className="h-24 w-full" />
          </div>
        ) : rows.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted">{t("empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-left text-xs text-muted">
                <tr>
                  <th className="px-3 py-2">{t("name")}</th>
                  <th className="px-3 py-2">{t("mobile")}</th>
                  <th className="px-3 py-2">{t("panchayat")}</th>
                  <th className="px-3 py-2">{t("crop")}</th>
                  <th className="px-3 py-2">{t("language")}</th>
                  <th className="px-3 py-2">{t("source")}</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((f) => (
                  <tr key={f.id}>
                    <td className="px-3 py-2 font-medium">{f.name ?? "–"}</td>
                    <td className="px-3 py-2 font-mono">{f.mobile_masked}</td>
                    <td className="px-3 py-2">{localName(f.panchayat, locale)}</td>
                    <td className="px-3 py-2">{f.crop ?? "–"}</td>
                    <td className="px-3 py-2">{LANG_LABEL[f.language] ?? f.language}</td>
                    <td className="px-3 py-2 text-xs">{f.source === "self" ? t("srcSelf") : t("srcUpload")}</td>
                    <td className="px-3 py-2 text-right">
                      <Button variant="ghost" size="icon" onClick={() => remove(f.id)} aria-label={t("remove")}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
