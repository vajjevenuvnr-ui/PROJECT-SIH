import { AlertTriangle, CheckCircle2, Share2, XCircle, type LucideIcon } from "lucide-react";
import type { Metadata, Viewport } from "next";
import { createTranslator } from "next-intl";
import { headers } from "next/headers";

import { Logo } from "@/components/brand/Logo";
import { FarmerRuntime } from "@/components/farmer/FarmerRuntime";
import { GetAlertsButton } from "@/components/farmer/GetAlertsButton";
import { ListenButton } from "@/components/farmer/ListenButton";
import { RainFeedback } from "@/components/farmer/RainFeedback";
import { SmsSignup } from "@/components/farmer/SmsSignup";
import { SosAlert, type FarmerWarning } from "@/components/farmer/SosAlert";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { localeNames, type Locale } from "@/i18n/config";
import type { AdvisoryItem, AdvisoryTag, Confidence, Lang } from "@/lib/types";
import { cn } from "@/lib/utils";
import { num, weatherIcon } from "@/lib/weather";

// S7: public, no-login farmer page opened from the SMS/WhatsApp link.
// Server-rendered so it arrives as ready HTML on 2G/3G; only small widgets ship JavaScript.

export const dynamic = "force-dynamic";

const LANGS: Lang[] = ["te", "en", "hi"];
const BACKEND = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

interface PublicDay {
  day: number;
  date: string;
  rain_mm: number;
  rain_prob_10mm: number | null;
  rain_prob_2_5mm: number | null;
  tmax: number;
  tmin: number;
  confidence: Confidence;
}

interface PublicPayload {
  panchayat: { id: number; name: string; name_en: string; block: string };
  today: PublicDay;
  days: PublicDay[];
  confidence: { level: Confidence; text: string };
  advisory: { id: number; items: AdvisoryItem[] } | null;
  issued_at: string;
  source_label: string;
  warnings?: FarmerWarning[];
}

const TAGS: Record<AdvisoryTag, { icon: LucideIcon; box: string; icon_cls: string }> = {
  avoid: { icon: XCircle, box: "border-danger/40 bg-danger/10", icon_cls: "bg-danger text-white" },
  prepare: { icon: AlertTriangle, box: "border-accent/60 bg-accent/15", icon_cls: "bg-accent text-accent-foreground" },
  do_now: { icon: CheckCircle2, box: "border-success/40 bg-success/10", icon_cls: "bg-success text-white" },
};

function pickLang(v: string | string[] | undefined): Lang {
  const s = Array.isArray(v) ? v[0] : v;
  return s === "en" || s === "hi" || s === "te" ? s : "te";
}

async function load(id: number, lang: Lang): Promise<PublicPayload | null> {
  try {
    const res = await fetch(`${BACKEND}/api/public/panchayat/${id}?lang=${lang}`, { cache: "no-store" });
    return res.ok ? ((await res.json()) as PublicPayload) : null;
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  return {
    title: "Kshetra",
    manifest: `/f/${Number(params.id) || 0}/manifest.webmanifest`,
    icons: { icon: "/brand/favicon.png", apple: "/brand/icon-192.png" },
  };
}

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0B5D4B" };

export default async function FarmerPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { lang?: string | string[]; sos?: string | string[] };
}) {
  const id = Number(params.id);
  const lang = pickLang(searchParams.lang);
  // The farmer chooses the language with ?lang= (independent of the officer's cookie).
  const messages = (await import(`@/messages/${lang}.json`)).default;
  const t = createTranslator({ locale: lang, messages, namespace: "farmer" });
  const data = await load(id, lang);

  const h = headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const proto = h.get("x-forwarded-proto") ?? "http";
  const pageUrl = `${proto}://${host}/f/${id}?lang=${lang}`;
  const intlLocale = `${lang}-IN`;
  const fmt = (iso: string, o: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat(intlLocale, { timeZone: "Asia/Kolkata", ...o }).format(new Date(iso));

  const header = (
    <header className="flex items-center justify-between gap-2">
      <Logo size="sm" priority />
      <div className="flex items-center gap-2">
        <nav aria-label="Language" className="flex rounded-full border bg-surface p-0.5 text-sm font-bold">
          {LANGS.map((l) => (
            <a
              key={l}
              href={`?lang=${l}`}
              aria-current={l === lang ? "true" : undefined}
              className={cn("rounded-full px-3 py-1.5", l === lang ? "bg-primary text-primary-foreground" : "text-muted")}
            >
              {l.toUpperCase()}
            </a>
          ))}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );

  if (!data) {
    return (
      <main lang={lang} className="mx-auto flex min-h-screen max-w-md flex-col gap-4 bg-background px-4 py-4">
        {header}
        <FarmerRuntime offlineText={t("offline")} />
        <div className="rounded-3xl border bg-surface p-6 text-center shadow-card">
          <p className="text-lg font-semibold">{t("error")}</p>
          <a href={`?lang=${lang}`} className="mt-4 inline-flex h-12 items-center rounded-2xl bg-primary px-6 font-bold text-primary-foreground">
            {t("retry")}
          </a>
        </div>
      </main>
    );
  }

  const { panchayat: gp, today, days, advisory, confidence } = data;
  const TodayIcon = weatherIcon(today.rain_mm, today.rain_prob_10mm, today.tmax);
  const chance = Math.round((today.rain_prob_2_5mm ?? today.rain_prob_10mm ?? 0) * 100);
  const actions = (advisory?.items ?? []).slice(0, 3);
  const speech = [
    gp.name,
    `${t("today")}: ${num(today.tmax, 0)} / ${num(today.tmin, 0)} °C, ${t("rainChance", { p: chance })}`,
    ...actions.map((a) => a.title[lang]),
    confidence.text,
  ].join(". ");
  const topWarning = (data.warnings ?? [])[0];
  const sos = String(searchParams.sos ?? "") === "1";
  const shareHref = `https://wa.me/?text=${encodeURIComponent(`${gp.name} · Kshetra\n${pageUrl}`)}`;

  return (
    <main lang={lang} className="mx-auto flex min-h-screen max-w-md flex-col gap-4 bg-background px-4 pb-10 pt-4">
      {header}
      <FarmerRuntime offlineText={t("offline")} />

      {topWarning && (
        <SosAlert
          warning={topWarning}
          fullscreen={sos}
          lang={lang}
          dayLabel={fmt(topWarning.date, { weekday: "long", day: "numeric", month: "short" })}
          labels={{ title: t("sosTitle"), tap: t("sosTap"), doNow: t("sosDo"), close: t("sosClose"), simulated: t("sosSimulated") }}
        />
      )}

      {/* Today */}
      <section className="rounded-3xl bg-primary p-5 text-primary-foreground shadow-card">
        <h1 className="text-3xl font-bold leading-tight">{gp.name}</h1>
        <p className="text-sm opacity-80">{t("block", { block: gp.block })}</p>
        <div className="mt-4 flex items-center gap-4">
          <TodayIcon className="h-16 w-16 shrink-0" aria-hidden />
          <div>
            <p className="text-sm font-semibold opacity-85">
              {t("today")} · {fmt(today.date, { weekday: "long", day: "numeric", month: "short" })}
            </p>
            <p className="text-4xl font-extrabold leading-none">
              {num(today.tmax, 0)}° <span className="text-2xl font-bold opacity-80">/ {num(today.tmin, 0)}°</span>
            </p>
            <p className="mt-1 text-lg font-bold">{t("rainChance", { p: chance })}</p>
          </div>
        </div>
        <p className="mt-4 inline-flex rounded-full bg-primary-foreground/15 px-3 py-1 text-sm font-semibold">{confidence.text}</p>
      </section>

      {/* Actions */}
      <section aria-labelledby="actions" className="flex flex-col gap-3">
        <h2 id="actions" className="text-xl font-bold">
          {t("actions")}
        </h2>
        {actions.length === 0 && <p className="rounded-2xl border bg-surface p-4 text-muted">{t("noAdvice")}</p>}
        {actions.map((a) => {
          const s = TAGS[a.tag];
          const Icon = s.icon;
          return (
            <article key={a.id} className={cn("flex gap-3 rounded-2xl border-2 p-4", s.box)}>
              <span className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-full", s.icon_cls)}>
                <Icon className="h-7 w-7" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="text-xs font-bold uppercase tracking-wide text-muted">{t(`tags.${a.tag}`)}</p>
                <p className="text-lg font-bold leading-snug">{a.title[lang]}</p>
                <p className="mt-1 text-sm text-muted">{a.reason[lang]}</p>
              </div>
            </article>
          );
        })}
      </section>

      <div className="flex gap-3">
        <ListenButton
          text={speech}
          lang={lang}
          labels={{ listen: t("listen"), stop: t("stop"), noVoice: t("noVoice"), langNames: localeNames as Record<Locale, string> }}
        />
        <a
          href={shareHref}
          target="_blank"
          rel="noreferrer"
          aria-label={t("share")}
          className="flex h-14 w-16 shrink-0 items-center justify-center rounded-2xl border-2 border-success bg-surface text-success shadow-card"
        >
          <Share2 className="h-6 w-6" aria-hidden />
        </a>
      </div>

      {/* 5-day strip */}
      <section aria-labelledby="days">
        <h2 id="days" className="mb-2 text-xl font-bold">
          {t("fiveDay")}
        </h2>
        <div className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2">
          {days.map((d) => {
            const Icon = weatherIcon(d.rain_mm, d.rain_prob_10mm, d.tmax);
            return (
              <div key={d.day} className="flex min-w-[6.5rem] snap-start flex-col items-center gap-1 rounded-2xl border bg-surface px-3 py-3 shadow-card">
                <p className="font-bold">{fmt(d.date, { weekday: "short" })}</p>
                <Icon className="h-9 w-9 text-info" aria-hidden />
                <p className="text-lg font-extrabold">
                  {num(d.tmax, 0)}°<span className="text-sm font-semibold text-muted">/{num(d.tmin, 0)}°</span>
                </p>
                <p className="text-sm font-semibold text-info">{num(d.rain_mm)} mm</p>
              </div>
            );
          })}
        </div>
      </section>

      <GetAlertsButton
        panchayatId={gp.id}
        lang={lang}
        labels={{ get: t("getAlerts"), on: t("alertsOn"), blocked: t("alertsBlocked"), needHttps: t("alertsNeedHttps") }}
      />

      <SmsSignup
        panchayatId={gp.id}
        lang={lang}
        labels={{
          title: t("sms.title"),
          body: t("sms.body"),
          mobile: t("sms.mobile"),
          name: t("sms.name"),
          consent: t("sms.consent"),
          submit: t("sms.submit"),
          done: t("sms.done", { mobile: "{mobile}" }),
          invalid: t("sms.invalid"),
          error: t("sms.error"),
          stop: t("sms.stop"),
          stopped: t("sms.stopped"),
        }}
      />

      <RainFeedback
        panchayatId={gp.id}
        labels={{ question: t("rainedQ"), yes: t("yes"), no: t("no"), thanks: t("thanks"), already: t("already") }}
      />

      <footer className="mt-2 text-center text-xs text-muted">
        <p>{t("issued", { time: fmt(data.issued_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }) })}</p>
        <p>
          {t("basedOn")} · {data.source_label}
        </p>
      </footer>
    </main>
  );
}
