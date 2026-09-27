"use client";

import {
  Bell,
  CheckCircle2,
  Download,
  ExternalLink,
  GitCompareArrows,
  FlaskConical,
  Loader2,
  RotateCcw,
  Send,
  Siren,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useSWRConfig } from "swr";

import { ConfidencePill } from "@/components/data/ConfidencePill";
import { useApi, useDemo, useRegion } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { localName } from "@/lib/names";
import { audioReady, playSiren, unlockAudio, vibrateAlert } from "@/lib/siren";
import type { AlertLevel, AlertsResponse, BlockSummary, DispatchResult, Lang, Warning } from "@/lib/types";
import { cn } from "@/lib/utils";

type Change = {
  panchayat_id: number;
  date: string;
  kind: "rain" | "confidence" | "alert";
  severity: "high" | "medium" | "low";
  text: Record<Lang, string>;
};
type ChangesResponse = { compared_with: string | null; changes: Change[] };

const SEVERITY_STYLE: Record<Change["severity"], string> = {
  high: "border-l-danger",
  medium: "border-l-accent",
  low: "border-l-muted",
};

/** Only what changed since the previous forecast run, so the officer need not re-read everything. */
function useChanges() {
  const { selection } = useRegion();
  return useApi<ChangesResponse>(selection.blockId ? `/api/alerts/changes?block_id=${selection.blockId}` : null, {
    refreshInterval: 30_000,
  });
}

function ChangesSection({ onNavigate }: { onNavigate: () => void }) {
  const t = useTranslations("changes");
  const locale = useLocale() as Lang;
  const { data } = useChanges();
  if (!data) return null;
  return (
    <section className="rounded-xl border bg-surface p-4">
      <h3 className="flex items-center justify-between gap-2 text-sm font-bold">
        <span className="flex items-center gap-2">
          <GitCompareArrows className="h-4 w-4 text-primary" aria-hidden /> {t("title")}
        </span>
        <span className="text-xs font-semibold text-muted">{t("count", { n: data.changes.length })}</span>
      </h3>
      {data.compared_with && <p className="mt-0.5 text-xs text-muted">{t("compared", { what: data.compared_with })}</p>}
      {data.changes.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("none")}</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-1.5">
          {data.changes.slice(0, 12).map((c, i) => (
            <li key={i} className={cn("border-l-4 pl-2 text-sm", SEVERITY_STYLE[c.severity])}>
              <Link href={`/panchayat/${c.panchayat_id}`} onClick={onNavigate} className="hover:underline">
                {c.text[locale]}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const SOUND_KEY = "pc-alert-sound";
const PLAYED_KEY = "pc-sirens-played";
const RANK: Record<AlertLevel, number> = { yellow: 0, orange: 1, red: 2 };

export const LEVEL_STYLE: Record<AlertLevel, string> = {
  yellow: "bg-alert-yellow text-alert-on-yellow",
  orange: "bg-alert-orange text-alert-on-orange",
  red: "bg-alert-red text-alert-on-red",
};

function readSet(key: string): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(key) ?? "[]"));
  } catch {
    return new Set();
  }
}

interface AlertState {
  data: AlertsResponse | undefined;
  unacked: Warning[];
  soundOn: boolean;
  needsGesture: boolean;
  drawerOpen: boolean;
  setDrawerOpen: (v: boolean) => void;
  setSound: (on: boolean) => Promise<void>;
  enableAudio: () => Promise<void>;
  simulate: () => Promise<void>;
  reset: () => Promise<void>;
  ack: (id: string) => Promise<void>;
  dispatch: (id: string) => Promise<DispatchResult | null>;
  busy: string | null;
  results: Record<string, DispatchResult>;
}

const AlertContext = createContext<AlertState | null>(null);

export function useAlerts() {
  const ctx = useContext(AlertContext);
  if (!ctx) throw new Error("useAlerts must be used inside AlertProvider");
  return ctx;
}

/** Polls the block's IMD colour-coded warnings, plays the siren once per new Orange/Red alert. */
export function AlertProvider({ children }: { children: React.ReactNode }) {
  const { demo } = useDemo();
  const { selection } = useRegion();
  const { mutate: mutateAll } = useSWRConfig();
  const path = selection.blockId ? `/api/alerts?block_id=${selection.blockId}` : null;
  const { data, mutate } = useApi<AlertsResponse>(path, { refreshInterval: 15_000, dedupingInterval: 2_000 });

  const [soundOn, setSoundOn] = useState(false);
  const [needsGesture, setNeedsGesture] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, DispatchResult>>({});
  const played = useRef<Set<string>>(new Set());

  useEffect(() => {
    played.current = readSet(PLAYED_KEY);
    try {
      setSoundOn(localStorage.getItem(SOUND_KEY) === "1");
    } catch {}
  }, []);

  const unacked = useMemo(
    () =>
      (data?.alerts ?? [])
        .filter((a) => !data?.acknowledged[a.id])
        .sort((a, b) => RANK[b.level] - RANK[a.level] || a.day - b.day),
    [data],
  );

  // Siren: once per new, unacknowledged Orange/Red alert with enough confidence.
  useEffect(() => {
    const fresh = unacked.filter((a) => a.siren && !played.current.has(a.id));
    if (!fresh.length || !soundOn) {
      setNeedsGesture(false);
      return;
    }
    if (playSiren()) {
      vibrateAlert();
      fresh.forEach((a) => played.current.add(a.id));
      try {
        localStorage.setItem(PLAYED_KEY, JSON.stringify(Array.from(played.current).slice(-200)));
      } catch {}
      setNeedsGesture(false);
    } else {
      setNeedsGesture(true); // browser blocked audio until the officer taps something
    }
  }, [unacked, soundOn]);

  const enableAudio = useCallback(async () => {
    await unlockAudio();
    setNeedsGesture(!audioReady());
    mutate(); // re-run the siren check now that audio is allowed
  }, [mutate]);

  const setSound = useCallback(
    async (on: boolean) => {
      if (on) await unlockAudio();
      setSoundOn(on);
      try {
        localStorage.setItem(SOUND_KEY, on ? "1" : "0");
      } catch {}
      if (on && audioReady()) playSiren(1, 0.12); // short confirmation
    },
    [],
  );

  const refreshEverything = useCallback(() => mutateAll(() => true, undefined, { revalidate: true }), [mutateAll]);

  const simulate = useCallback(async () => {
    await unlockAudio(); // the click is a user gesture: allow the siren that follows
    setBusy("simulate");
    try {
      await api("/api/demo/simulate-extreme", { demo, method: "POST", body: {} });
      await refreshEverything();
    } finally {
      setBusy(null);
    }
  }, [demo, refreshEverything]);

  const reset = useCallback(async () => {
    setBusy("reset");
    try {
      await api("/api/demo/reset-simulation", { demo, method: "POST" });
      setResults({});
      await refreshEverything();
    } finally {
      setBusy(null);
    }
  }, [demo, refreshEverything]);

  const ack = useCallback(
    async (id: string) => {
      setBusy(`ack:${id}`);
      try {
        await api(`/api/alerts/${encodeURIComponent(id)}/ack`, { demo, method: "POST" });
        await mutate();
      } finally {
        setBusy(null);
      }
    },
    [demo, mutate],
  );

  const dispatch = useCallback(
    async (id: string) => {
      setBusy(`send:${id}`);
      try {
        const r = await api<DispatchResult>(`/api/alerts/${encodeURIComponent(id)}/dispatch`, { demo, method: "POST" });
        setResults((prev) => ({ ...prev, [id]: r }));
        return r;
      } catch {
        return null;
      } finally {
        setBusy(null);
      }
    },
    [demo],
  );

  const value: AlertState = {
    data,
    unacked,
    soundOn,
    needsGesture,
    drawerOpen,
    setDrawerOpen,
    setSound,
    enableAudio,
    simulate,
    reset,
    ack,
    dispatch,
    busy,
    results,
  };
  return (
    <AlertContext.Provider value={value}>
      {children}
      <AlertDrawer />
    </AlertContext.Provider>
  );
}

/** Bell in the top bar with the number of unacknowledged warnings. */
export function AlertBell() {
  const t = useTranslations("alertCenter");
  const { unacked, setDrawerOpen } = useAlerts();
  const changes = useChanges().data?.changes.length ?? 0;
  const top = unacked[0]?.level;
  return (
    <button
      type="button"
      onClick={() => setDrawerOpen(true)}
      aria-label={`${t("open")} (${unacked.length})`}
      title={t("title")}
      className="relative inline-flex h-9 w-9 items-center justify-center rounded-full border bg-surface text-foreground transition-colors hover:bg-surface-2"
    >
      <Bell className={cn("h-4 w-4", top && top !== "yellow" && "animate-pulse")} aria-hidden />
      {unacked.length > 0 && (
        <span
          className={cn(
            "absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[10px] font-bold",
            LEVEL_STYLE[top ?? "yellow"],
          )}
        >
          {unacked.length}
        </span>
      )}
      {unacked.length === 0 && changes > 0 && (
        <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-primary" aria-hidden />
      )}
    </button>
  );
}

/** Colour-coded banner under the top bar on every officer screen. */
export function AlertBanner() {
  const t = useTranslations("alertCenter");
  const locale = useLocale() as Lang;
  const format = useFormatter();
  const { unacked, setDrawerOpen, needsGesture, enableAudio, data } = useAlerts();
  if (!unacked.length) return null;
  const top = unacked[0];
  const others = unacked.filter((a) => a.level === top.level).length - 1;
  return (
    <div role="alert" className={cn("flex flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2.5 text-sm font-semibold", LEVEL_STYLE[top.level])}>
      <Siren className={cn("h-5 w-5 shrink-0", top.level !== "yellow" && "animate-pulse")} aria-hidden />
      <span className="min-w-0 flex-1">
        {t("banner", {
          title: top.title[locale],
          gp: localName(top.panchayat, locale),
          more: others > 0 ? t("more", { n: others }) : "",
          day: format.dateTime(new Date(top.date), { weekday: "long", day: "numeric", month: "short" }),
        })}
        {data?.simulation && <span className="ml-2 rounded bg-black/15 px-1.5 py-0.5 text-[11px] font-bold uppercase">{t("simulated")}</span>}
      </span>
      {needsGesture && (
        <button onClick={enableAudio} className="inline-flex items-center gap-1 rounded-full bg-black/15 px-3 py-1 text-xs font-bold">
          <Volume2 className="h-3.5 w-3.5" aria-hidden /> {t("enableSound")}
        </button>
      )}
      <button onClick={() => setDrawerOpen(true)} className="rounded-full bg-black/15 px-3 py-1 text-xs font-bold hover:bg-black/25">
        {t("view")}
      </button>
    </div>
  );
}

function AlertDrawer() {
  const t = useTranslations("alertCenter");
  const tc = useTranslations("confidence");
  const locale = useLocale() as Lang;
  const format = useFormatter();
  const { demo } = useDemo();
  const { selection } = useRegion();
  const summary = useApi<BlockSummary>(selection.blockId ? `/api/blocks/${selection.blockId}/summary` : null);
  const s = useAlerts();
  const { drawerOpen, setDrawerOpen } = s;

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen, setDrawerOpen]);

  if (!drawerOpen) return null;
  const alerts = s.data?.alerts ?? [];

  return (
    <div className="fixed inset-0 z-[1200] flex justify-end" role="dialog" aria-modal="true" aria-label={t("title")}>
      <button className="absolute inset-0 bg-foreground/40" aria-label={t("close")} onClick={() => setDrawerOpen(false)} />
      <aside className="relative flex h-full w-full max-w-md flex-col overflow-hidden bg-background shadow-card animate-fade-up">
        <header className="flex items-start justify-between gap-3 border-b bg-surface px-5 py-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold">
              <Siren className="h-5 w-5 text-danger" aria-hidden /> {t("title")}
            </h2>
            <p className="mt-0.5 text-xs text-muted">
              {t("subtitle", { block: summary.data ? localName(summary.data.block, locale) : "…" })}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={() => setDrawerOpen(false)} aria-label={t("close")}>
            <X />
          </Button>
        </header>

        <div className="flex flex-col gap-3 overflow-y-auto p-4">
          {/* Sound + demo controls */}
          <div className="flex items-center justify-between gap-3 rounded-xl border bg-surface px-4 py-3">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-sm font-semibold">
                {s.soundOn ? <Volume2 className="h-4 w-4 text-primary" /> : <VolumeX className="h-4 w-4 text-muted" />}
                {t("sound")}
              </p>
              <p className="text-xs text-muted">{t("soundHint")}</p>
            </div>
            <Switch checked={s.soundOn} onCheckedChange={(v) => s.setSound(v)} aria-label={t("sound")} />
          </div>

          {demo && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed bg-surface px-4 py-3">
              <FlaskConical className="h-4 w-4 text-warning" aria-hidden />
              <span className="mr-auto text-xs font-semibold text-muted">{t("demoOnly")}</span>
              {s.data?.simulation ? (
                <Button size="sm" variant="secondary" onClick={s.reset} disabled={s.busy !== null}>
                  {s.busy === "reset" ? <Loader2 className="animate-spin" /> : <RotateCcw />} {t("reset")}
                </Button>
              ) : (
                <Button size="sm" variant="danger" onClick={s.simulate} disabled={s.busy !== null}>
                  {s.busy === "simulate" ? <Loader2 className="animate-spin" /> : <Siren />}
                  {s.busy === "simulate" ? t("simulating") : t("simulate")}
                </Button>
              )}
            </div>
          )}

          {s.data?.simulation && (
            <p className="rounded-lg bg-accent/20 px-3 py-2 text-xs font-bold uppercase tracking-wide">{t("simulated")}</p>
          )}
          {s.data && !s.data.push_enabled && <p className="text-xs text-muted">{t("pushOff")}</p>}

          <ChangesSection onNavigate={() => setDrawerOpen(false)} />

          {alerts.length === 0 && <p className="py-8 text-center text-sm text-muted">{t("none")}</p>}

          {alerts.map((a) => {
            const acked = !!s.data?.acknowledged[a.id];
            const result = s.results[a.id];
            return (
              <article key={a.id} className={cn("overflow-hidden rounded-xl border bg-surface", acked && "opacity-70")}>
                <div className={cn("flex items-center justify-between gap-2 px-4 py-2 text-sm font-bold", LEVEL_STYLE[a.level])}>
                  <span>{a.title[locale]}</span>
                  <span className="text-xs">{format.dateTime(new Date(a.date), { weekday: "short", day: "numeric", month: "short" })}</span>
                </div>
                <div className="flex flex-col gap-2 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-base font-bold">{localName(a.panchayat, locale)}</p>
                    <p className="text-lg font-extrabold">
                      {a.value} {a.unit}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                    <ConfidencePill level={a.confidence} label={tc(a.confidence)} className="text-[9px]" />
                    {a.siren && <span className="inline-flex items-center gap-1 font-semibold text-danger"><Siren className="h-3 w-3" /> siren</span>}
                    {acked && (
                      <span className="inline-flex items-center gap-1 font-semibold text-success">
                        <CheckCircle2 className="h-3 w-3" /> {t("acked")}
                      </span>
                    )}
                  </div>
                  <p className="text-sm">{a.body[locale]}</p>
                  {result && (
                    <p className="rounded-lg bg-success/10 px-3 py-2 text-xs font-semibold text-success">
                      {t("sent", {
                        push: `${result.push.sent}/${result.push.subscribers}`,
                        sms: result.log.find((l) => l.channel === "sms_alert")?.recipients ?? 0,
                        voice: result.log.find((l) => l.channel === "voice_alert")?.recipients ?? 0,
                      })}
                    </p>
                  )}
                  <div className="mt-1 flex flex-wrap gap-2">
                    {!acked && (
                      <Button size="sm" variant="secondary" onClick={() => s.ack(a.id)} disabled={s.busy !== null}>
                        {s.busy === `ack:${a.id}` ? <Loader2 className="animate-spin" /> : <CheckCircle2 />} {t("ack")}
                      </Button>
                    )}
                    <Button size="sm" onClick={() => s.dispatch(a.id)} disabled={s.busy !== null}>
                      {s.busy === `send:${a.id}` ? <Loader2 className="animate-spin" /> : <Send />}
                      {s.busy === `send:${a.id}` ? t("sending") : t("send")}
                    </Button>
                    <Button size="sm" variant="ghost" asChild>
                      <a href={`/api/alerts/${encodeURIComponent(a.id)}/cap`} download>
                        <Download /> {t("cap")}
                      </a>
                    </Button>
                    <Button size="sm" variant="ghost" asChild>
                      <Link href={`/panchayat/${a.panchayat_id}`} onClick={() => setDrawerOpen(false)}>
                        <ExternalLink /> {t("viewGp")}
                      </Link>
                    </Button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </aside>
    </div>
  );
}
