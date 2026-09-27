"use client";

import {
  CalendarDays,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Ban,
  Check,
  CheckCircle2,
  ChevronDown,
  Flower2,
  Loader2,
  Pencil,
  Sprout,
  Wheat,
  type LucideIcon,
} from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ConfidencePill } from "@/components/data/ConfidencePill";
import { useApi, useDemo } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import { localeNames, type Locale } from "@/i18n/config";
import { api } from "@/lib/api";

type CropProfile = {
  panchayat_id: number;
  crop: string;
  sowing_date: string;
  is_default: boolean;
  stage: string;
  stage_name: Record<Lang, string>;
  days_since_sowing: number;
};
import { localName } from "@/lib/names";
import type { Advisory, AdvisoryItem, AdvisoryTag, CropInfo, Lang, PanchayatForecast } from "@/lib/types";
import { cn } from "@/lib/utils";
import { num } from "@/lib/weather";

const CROP_ICONS: Record<string, LucideIcon> = { cotton: Flower2, paddy: Wheat, maize: Sprout };

const TAG_STYLE: Record<AdvisoryTag, { icon: LucideIcon; badge: string; border: string }> = {
  avoid: { icon: Ban, badge: "bg-danger text-white", border: "border-l-danger" },
  prepare: { icon: AlertTriangle, badge: "bg-accent text-accent-foreground", border: "border-l-accent" },
  do_now: { icon: CheckCircle2, badge: "bg-success text-white", border: "border-l-success" },
};

export function AdvisoryView({ panchayatId }: { panchayatId: number }) {
  const t = useTranslations("advisory");
  const tc = useTranslations("confidence");
  const locale = useLocale() as Locale;
  const lang = locale as Lang;
  const router = useRouter();
  const { demo } = useDemo();

  const crops = useApi<CropInfo[]>("/api/advisory/crops");
  const fc = useApi<PanchayatForecast>(`/api/forecast/panchayat/${panchayatId}`);

  const tp = useTranslations("profile");
  const profile = useApi<CropProfile>(`/api/crop-profiles/${panchayatId}`);
  const [prefilled, setPrefilled] = useState(false);
  const [editProfile, setEditProfile] = useState(false);
  const [sowing, setSowing] = useState("");
  const [profileMsg, setProfileMsg] = useState<string | null>(null);
  const [crop, setCrop] = useState("cotton");
  const [stage, setStage] = useState<string | null>(null);
  const [advisory, setAdvisory] = useState<Advisory | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<AdvisoryItem[]>([]);
  const [busy, setBusy] = useState<"save" | "approve" | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Generate whenever crop + stage change (ignore stale responses).
  useEffect(() => {
    if (!stage) return;
    let cancelled = false;
    setGenerating(true);
    setError(null);
    setEditing(false);
    api<Advisory>("/api/advisory/generate", {
      demo,
      method: "POST",
      body: { panchayat_id: panchayatId, crop, stage, lang },
    })
      .then((a) => {
        if (cancelled) return;
        setAdvisory(a);
        setDraft(a.items);
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setGenerating(false));
    return () => {
      cancelled = true;
    };
    // `lang` is not a dependency: items carry all three languages.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [crop, stage, panchayatId, demo]);

  // Pre-fill crop + stage from the panchayat's crop profile (sowing date -> stage), once.
  useEffect(() => {
    if (prefilled || !profile.data) return;
    setCrop(profile.data.crop);
    setStage(profile.data.stage);
    setSowing(profile.data.sowing_date);
    setPrefilled(true);
  }, [profile.data, prefilled]);

  const saveProfile = async () => {
    try {
      const p = await api<CropProfile>(`/api/crop-profiles/${panchayatId}`, {
        demo,
        method: "PUT",
        body: { crop, sowing_date: sowing },
      });
      void profile.mutate(p, { revalidate: false });
      setStage(p.stage);
      setEditProfile(false);
      setProfileMsg(tp("saved"));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const cropInfo = crops.data?.find((c) => c.id === crop);
  const items = editing ? draft : (advisory?.items ?? []);

  const save = async (): Promise<Advisory | null> => {
    if (!advisory) return null;
    setBusy("save");
    try {
      const updated = await api<Advisory>(`/api/advisory/${advisory.id}`, {
        demo,
        method: "PATCH",
        body: { items: draft },
      });
      setAdvisory(updated);
      setDraft(updated.items);
      setSavedAt(Date.now());
      setEditing(false);
      return updated;
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setBusy(null);
    }
  };

  const approve = async () => {
    if (!advisory) return;
    if (editing && !(await save())) return;
    setBusy("approve");
    try {
      const a = await api<Advisory>(`/api/advisory/${advisory.id}/approve`, { demo, method: "POST" });
      router.push(`/share/${a.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  };

  const editText = (idx: number, field: "title" | "reason", value: string) =>
    setDraft((prev) =>
      prev.map((it, i) => (i === idx ? { ...it, [field]: { ...it[field], [lang]: value }, edited: true } : it)),
    );

  if (fc.error) return <ErrorCard message={fc.error.message} onRetry={() => fc.mutate()} />;
  const gp = fc.data?.panchayat;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      {/* Header */}
      <Card className="flex flex-col gap-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <Button asChild variant="ghost" size="sm" className="-ml-2 shrink-0">
              <Link href={`/panchayat/${panchayatId}`}>
                <ArrowLeft />
              </Link>
            </Button>
            <div className="min-w-0">
              {gp ? (
                <h1 className="text-2xl font-bold leading-tight">
                  {t("title")} · {localName(gp, locale)}
                </h1>
              ) : (
                <Skeleton className="h-7 w-64" />
              )}
              <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>
            </div>
          </div>
          {gp && <ConfidencePill level={gp.confidence} label={tc(gp.confidence)} />}
        </div>

        {/* Crop profile */}
        {profile.data && (
          <div className="rounded-xl border bg-surface-2 p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <CalendarDays className="h-4 w-4 text-primary" aria-hidden />
              <span>
                {tp("fromProfile", {
                  crop: crops.data?.find((c) => c.id === profile.data!.crop)?.name[lang] ?? profile.data.crop,
                  date: profile.data.sowing_date,
                  days: profile.data.days_since_sowing,
                  stage: profile.data.stage_name[lang],
                })}
              </span>
              {profile.data.is_default && <span className="text-xs text-muted">({tp("default")})</span>}
              {profileMsg && <span className="text-xs text-success">{profileMsg}</span>}
              <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setEditProfile((v) => !v)}>
                {editProfile ? tp("cancel") : tp("edit")}
              </Button>
            </div>
            {editProfile && (
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <label className="text-xs font-medium">
                  {tp("sowing")}
                  <input
                    type="date"
                    value={sowing}
                    onChange={(e) => setSowing(e.target.value)}
                    className="mt-1 block rounded-md border bg-surface px-2 py-1 text-sm"
                  />
                </label>
                <Button size="sm" onClick={saveProfile} disabled={!sowing}>
                  {tp("save")}
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Crop */}
        <div>
          <p className="mb-2 text-sm font-medium">{t("crop")}</p>
          <div role="radiogroup" aria-label={t("crop")} className="grid grid-cols-3 gap-2 sm:max-w-md">
            {(crops.data ?? []).map((c) => {
              const Icon = CROP_ICONS[c.id] ?? Sprout;
              const active = crop === c.id;
              return (
                <button
                  key={c.id}
                  role="radio"
                  aria-checked={active}
                  onClick={() => {
                    setCrop(c.id);
                    setStage(null);
                    setAdvisory(null);
                  }}
                  className={cn(
                    "flex flex-col items-center gap-1 rounded-xl border px-3 py-3 text-sm font-semibold transition-colors",
                    active ? "border-primary bg-primary/10 text-primary" : "hover:bg-surface-2",
                  )}
                >
                  <Icon className="h-6 w-6" aria-hidden />
                  {c.name[lang]}
                </button>
              );
            })}
            {!crops.data && [0, 1, 2].map((i) => <Skeleton key={i} className="h-[74px]" />)}
          </div>
        </div>

        {/* Stage */}
        <div>
          <p className="mb-2 text-sm font-medium">{t("stage")}</p>
          <div role="radiogroup" aria-label={t("stage")} className="flex flex-wrap gap-2">
            {cropInfo?.stages.map((s) => {
              const active = stage === s.id;
              return (
                <button
                  key={s.id}
                  role="radio"
                  aria-checked={active}
                  onClick={() => setStage(s.id)}
                  className={cn(
                    "rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors",
                    active ? "border-primary bg-primary text-primary-foreground" : "hover:bg-surface-2",
                  )}
                >
                  {s.name[lang]}
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      {error && <ErrorCard message={error} onRetry={() => setError(null)} />}

      {/* Advisory cards */}
      {!stage && <p className="rounded-card border border-dashed bg-surface px-4 py-6 text-center text-muted">{t("pickStage")}</p>}

      {stage && generating && (
        <div className="flex flex-col gap-3" aria-busy>
          <p className="flex items-center gap-2 text-sm text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> {t("generating")}
          </p>
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      )}

      {stage && !generating && advisory && (
        <>
          {items.length === 0 ? (
            <p className="rounded-card border bg-surface px-4 py-6 text-center text-muted">{t("none")}</p>
          ) : (
            <div className="flex flex-col gap-3">
              {editing && (
                <p className="rounded-xl bg-info/10 px-3 py-2 text-sm text-info">
                  {t("editHint", { lang: localeNames[locale] })}
                </p>
              )}
              {items.map((it, idx) => (
                <AdvisoryCard
                  key={it.id}
                  item={it}
                  lang={lang}
                  editing={editing}
                  onEdit={(field, value) => editText(idx, field, value)}
                />
              ))}
            </div>
          )}

          <div className="sticky bottom-20 z-10 flex flex-wrap items-center justify-end gap-2 rounded-card border bg-surface/95 p-3 shadow-card backdrop-blur md:bottom-4">
            <span className="mr-auto text-xs text-muted">
              {advisory.status === "approved" ? t("approved") : t("draft")}
              {savedAt && ` · ${t("saved")}`}
            </span>
            {editing ? (
              <Button variant="secondary" onClick={save} disabled={busy !== null}>
                {busy === "save" ? <Loader2 className="animate-spin" /> : <Check />} {t("save")}
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => setEditing(true)} disabled={busy !== null || items.length === 0}>
                <Pencil /> {t("edit")}
              </Button>
            )}
            <Button onClick={approve} disabled={busy !== null || items.length === 0}>
              {busy === "approve" ? <Loader2 className="animate-spin" /> : null}
              {busy === "approve" ? t("approving") : t("approve")} <ArrowRight />
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function AdvisoryCard({
  item,
  lang,
  editing,
  onEdit,
}: {
  item: AdvisoryItem;
  lang: Lang;
  editing: boolean;
  onEdit: (field: "title" | "reason", value: string) => void;
}) {
  const t = useTranslations("advisory");
  const format = useFormatter();
  const [open, setOpen] = useState(false);
  const style = TAG_STYLE[item.tag];
  const Icon = style.icon;
  const weekday = (iso: string) => format.dateTime(new Date(iso), { weekday: "short" });
  const opText: Record<string, string> = { ">=": "≥", "<=": "≤", ">": ">", "<": "<", "==": "=" };

  return (
    <Card className={cn("overflow-hidden border-l-4", style.border)}>
      <div className="flex flex-col gap-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide", style.badge)}>
            <Icon className="h-3.5 w-3.5" aria-hidden /> {t(`tags.${item.tag}`)}
          </span>
          <span className="text-xs text-muted">
            {t("valid")}: {item.valid_days.map((d) => weekday(d.date)).join(", ")}
          </span>
          {item.edited && <span className="text-xs font-medium text-info">· {t("edited")}</span>}
        </div>

        {editing ? (
          <div className="flex flex-col gap-2">
            <label className="flex flex-col gap-1 text-xs font-medium text-muted">
              {t("titleField")}
              <input
                value={item.title[lang]}
                onChange={(e) => onEdit("title", e.target.value)}
                className="h-10 rounded-lg border bg-surface px-3 text-base font-semibold text-foreground outline-none focus-visible:border-primary"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-muted">
              {t("reasonField")}
              <textarea
                value={item.reason[lang]}
                onChange={(e) => onEdit("reason", e.target.value)}
                rows={2}
                className="rounded-lg border bg-surface px-3 py-2 text-sm text-foreground outline-none focus-visible:border-primary"
              />
            </label>
          </div>
        ) : (
          <>
            <h3 className="text-lg font-bold leading-snug">{item.title[lang]}</h3>
            <p className="text-sm text-muted">{item.reason[lang]}</p>
          </>
        )}

        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="mt-1 inline-flex items-center gap-1 self-start text-sm font-semibold text-primary hover:underline"
        >
          {open ? t("hideWhy") : t("why")}
          <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} aria-hidden />
        </button>
      </div>

      {open && (
        <div className="border-t bg-surface-2/60 px-4 py-3 text-sm">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            {t("ruleNote", { id: item.explain.rule_id })}
          </p>
          {item.explain.conditions.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[22rem] text-left">
                <thead className="text-xs text-muted">
                  <tr>
                    <th className="py-1 pr-3 font-medium">{t("condition")}</th>
                    <th className="py-1 pr-3 font-medium">{t("threshold")}</th>
                    <th className="py-1 pr-3 font-medium">{t("actual")}</th>
                    <th className="py-1 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {item.explain.conditions.map((c) => (
                    <tr key={c.metric} className="border-t border-border/60">
                      <td className="py-1.5 pr-3">{c.label[lang]}</td>
                      <td className="py-1.5 pr-3 font-mono text-xs">
                        {opText[c.op] ?? c.op} {num(c.threshold)} {c.unit}
                      </td>
                      <td className="py-1.5 pr-3 font-bold">
                        {num(c.actual)} {c.unit}
                      </td>
                      <td className="py-1.5">
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
                          <Check className="h-3.5 w-3.5" aria-hidden /> {t("met")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {item.explain.days_used.length > 0 && (
            <>
              <p className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-muted">{t("forecastUsed")}</p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[22rem] text-left text-xs">
                  <thead className="text-muted">
                    <tr>
                      <th className="py-1 pr-3 font-medium">{t("day")}</th>
                      <th className="py-1 pr-3 font-medium">{t("rain")}</th>
                      <th className="py-1 pr-3 font-medium">{t("chance10")}</th>
                      <th className="py-1 pr-3 font-medium">{t("tmax")}</th>
                      <th className="py-1 pr-3 font-medium">{t("rh")}</th>
                      <th className="py-1 font-medium">{t("wind")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {item.explain.days_used.map((d) => (
                      <tr key={d.day} className="border-t border-border/60">
                        <td className="py-1 pr-3 font-semibold">{weekday(d.date)}</td>
                        <td className="py-1 pr-3">{num(d.rain_mm)} mm</td>
                        <td className="py-1 pr-3">{d.rain_prob_10mm === null ? "–" : `${Math.round(d.rain_prob_10mm * 100)}%`}</td>
                        <td className="py-1 pr-3">{num(d.tmax)} °C</td>
                        <td className="py-1 pr-3">{num(d.rh, 0)}%</td>
                        <td className="py-1">{num(d.wind_kmh, 0)} km/h</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {item.id === "low_confidence" && <p className="text-muted">{t("explainLowConf")}</p>}
        </div>
      )}
    </Card>
  );
}
