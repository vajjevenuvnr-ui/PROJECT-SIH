"use client";

import { ArrowLeft, CheckCircle2, Copy, ExternalLink, Info, Loader2, MessageCircle, RotateCcw, Send, Smartphone, Users } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useApi, useDemo } from "@/components/providers/AppProviders";
import { PhoneMockup } from "@/components/share/PhoneMockup";
import { QrCode } from "@/components/share/QrCode";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import { localeNames } from "@/i18n/config";
import { api } from "@/lib/api";
import { localName } from "@/lib/names";
import { smsInfo } from "@/lib/sms";
import type { Advisory, FarmerMessage, Health, Lang, ShareLogEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

const LANGS: Lang[] = ["te", "hi", "en"];
type Channel = "sms" | "whatsapp";

/** Address a phone on the same Wi-Fi can open (LAN IP instead of localhost). */
function usePublicBase(health: Health | undefined): string | null {
  const [base, setBase] = useState<string | null>(null);
  useEffect(() => {
    const { hostname, port, protocol, origin } = window.location;
    const local = hostname === "localhost" || hostname === "127.0.0.1";
    if (local && health?.lan_ip) setBase(`${protocol}//${health.lan_ip}${port ? `:${port}` : ""}`);
    else if (!local || health) setBase(origin);
  }, [health]);
  return base;
}

export function ShareView({ advisoryId }: { advisoryId: number }) {
  const t = useTranslations("share");
  const locale = useLocale();
  const format = useFormatter();
  const { demo } = useDemo();

  const adv = useApi<Advisory>(`/api/advisory/${advisoryId}`);
  const health = useApi<Health>("/health");
  const base = usePublicBase(health.data);

  const [lang, setLang] = useState<Lang>("te");
  const [channel, setChannel] = useState<Channel>("whatsapp");
  const msgPath =
    adv.data && base
      ? `/api/advisory/${advisoryId}/message?lang=${lang}&channel=${channel}&base_url=${encodeURIComponent(base)}`
      : null;
  const msg = useApi<FarmerMessage>(msgPath);
  const log = useApi<ShareLogEntry[]>(`/api/share/log?advisory_id=${advisoryId}`);

  // Editable preview, reset whenever the generated message changes.
  const [text, setText] = useState("");
  useEffect(() => {
    if (msg.data) setText(msg.data.text);
  }, [msg.data]);
  const info = useMemo(() => smsInfo(text), [text]);
  const edited = !!msg.data && text !== msg.data.text;

  // Phone mockup state
  const [phone, setPhone] = useState<{ id: number; text: string; time: string }[]>([]);
  const [typing, setTyping] = useState(false);
  useEffect(() => setPhone([]), [channel]);

  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timeNow = () => format.dateTime(new Date(), { hour: "2-digit", minute: "2-digit", hour12: false });

  const send = async () => {
    setSending(true);
    setError(null);
    setSent(null);
    try {
      const entry = await api<ShareLogEntry>("/api/share", {
        demo,
        method: "POST",
        body: { advisory_id: advisoryId, channel, language: lang },
      });
      setTyping(true);
      const body = text;
      window.setTimeout(() => {
        setTyping(false);
        setPhone((p) => [...p, { id: entry.id, text: body, time: timeNow() }]);
      }, 900);
      setSent(entry.recipients);
      log.mutate();
      adv.mutate();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  if (adv.error) return <ErrorCard message={adv.error.message} onRetry={() => adv.mutate()} />;
  const a = adv.data;
  const gp = msg.data?.panchayat;
  const gpName = gp ? localName(gp, locale) : "";
  const isDraft = a?.status === "draft";
  const farmerHref = a ? `/f/${a.panchayat_id}?lang=${lang}` : "#";

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold sm:text-3xl">
            {t("title")}
            {gpName && <span className="text-muted"> · {gpName}</span>}
          </h1>
          <p className="mt-1 text-muted">{t("subtitle")}</p>
        </div>
        {a && (
          <Button asChild variant="ghost" size="sm">
            <Link href={`/panchayat/${a.panchayat_id}/advisory`}>
              <ArrowLeft /> {t("backToAdvisory")}
            </Link>
          </Button>
        )}
      </div>

      {isDraft && (
        <p className="flex items-center gap-2 rounded-card border-l-4 border-accent bg-accent/15 px-4 py-3 text-sm font-semibold">
          <Info className="h-4 w-4 text-warning" aria-hidden /> {t("notApproved")}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        {/* Left: controls */}
        <div className="flex min-w-0 flex-col gap-4">
          <Card className="flex flex-col gap-4 p-4 sm:p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-2 text-sm font-medium">{t("language")}</p>
                <div role="radiogroup" aria-label={t("language")} className="grid grid-cols-3 rounded-xl border bg-surface p-1">
                  {LANGS.map((l) => (
                    <button
                      key={l}
                      role="radio"
                      aria-checked={lang === l}
                      onClick={() => setLang(l)}
                      className={cn(
                        "rounded-lg py-2 text-sm font-semibold transition-colors",
                        lang === l ? "bg-primary text-primary-foreground" : "text-muted hover:text-foreground",
                      )}
                    >
                      {localeNames[l]}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-2 text-sm font-medium">{t("channel")}</p>
                <div role="radiogroup" aria-label={t("channel")} className="grid grid-cols-2 gap-2">
                  {(["sms", "whatsapp"] as const).map((c) => (
                    <button
                      key={c}
                      role="radio"
                      aria-checked={channel === c}
                      onClick={() => setChannel(c)}
                      className={cn(
                        "flex flex-col items-start rounded-xl border px-3 py-2 text-left transition-colors",
                        channel === c ? "border-primary bg-primary/10" : "hover:bg-surface-2",
                      )}
                    >
                      <span className="flex items-center gap-1.5 text-sm font-semibold">
                        {c === "sms" ? <Smartphone className="h-4 w-4" /> : <MessageCircle className="h-4 w-4" />}
                        {t(c)}
                      </span>
                      <span className="text-[11px] leading-tight text-muted">{c === "sms" ? t("smsHint") : t("waHint")}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <label htmlFor="msg" className="text-sm font-medium">
                  {t("preview")}
                </label>
                <div className="flex items-center gap-2 text-xs">
                  <span className="rounded-full bg-surface-2 px-2 py-0.5 text-muted">{t("chars", { chars: info.chars })}</span>
                  {channel === "sms" && (
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 font-semibold",
                        info.segments > 2 ? "bg-accent/25 text-foreground" : "bg-surface-2 text-muted",
                      )}
                      title={info.encoding === "UCS-2" ? t("ucs2Note") : undefined}
                    >
                      {t("segments", { n: info.segments, enc: info.encoding })}
                    </span>
                  )}
                  {edited && (
                    <button onClick={() => msg.data && setText(msg.data.text)} className="inline-flex items-center gap-1 text-primary hover:underline">
                      <RotateCcw className="h-3 w-3" /> {t("reset")}
                    </button>
                  )}
                </div>
              </div>
              {msg.data ? (
                <textarea
                  id="msg"
                  lang={lang}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={channel === "sms" ? 7 : 14}
                  className="w-full rounded-xl border bg-surface px-3 py-2.5 font-mono text-[13px] leading-relaxed outline-none focus-visible:border-primary"
                />
              ) : (
                <Skeleton className="h-44 w-full" />
              )}
              {channel === "sms" && info.encoding === "UCS-2" && <p className="mt-1.5 text-xs text-muted">{t("ucs2Note")}</p>}
            </div>

            <div className="flex flex-wrap items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5">
              <Users className="h-5 w-5 text-primary" aria-hidden />
              <p className="min-w-0 flex-1 text-sm">
                <span className="text-muted">{t("to")}: </span>
                <span className="font-semibold">{gp ? t("recipients", { gp: gpName, n: gp.registered_farmers }) : "…"}</span>
              </p>
              <Button variant="secondary" size="sm" onClick={copy} disabled={!text}>
                {copied ? <CheckCircle2 /> : <Copy />} {copied ? t("copied") : t("copy")}
              </Button>
              <Button size="lg" onClick={send} disabled={sending || isDraft || !msg.data}>
                {sending ? <Loader2 className="animate-spin" /> : <Send />} {sending ? t("sending") : t("send")}
              </Button>
            </div>

            {sent !== null && (
              <p role="status" className="flex items-center gap-2 text-sm font-semibold text-success">
                <CheckCircle2 className="h-4 w-4" aria-hidden /> {t("sentOk", { n: sent })}
              </p>
            )}
            {error && <p className="text-sm font-semibold text-danger">{error}</p>}
            <p className="text-xs text-muted">{t("simulated")}</p>
          </Card>

          {/* QR to open the farmer page on a phone */}
          <Card className="flex flex-col items-center gap-4 p-4 sm:flex-row sm:p-5">
            {msg.data ? <QrCode value={msg.data.link} /> : <Skeleton className="h-[148px] w-[148px]" />}
            <div className="flex min-w-0 flex-col gap-2 text-center sm:text-left">
              <p className="font-semibold">{t("scan")}</p>
              <p className="break-all font-mono text-xs text-muted">{msg.data?.link}</p>
              {!health.data?.lan_ip && <p className="text-xs text-muted">{t("noLan")}</p>}
              <Button asChild variant="secondary" size="sm" className="self-center sm:self-start">
                <a href={farmerHref} target="_blank" rel="noreferrer">
                  <ExternalLink /> {t("openFarmer")}
                </a>
              </Button>
            </div>
          </Card>
        </div>

        {/* Right: phone */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          <PhoneMockup
            channel={channel}
            sender={t("phoneFrom")}
            messages={phone}
            typing={typing}
            dayLabel={t("today")}
            lang={lang}
          />
        </div>
      </div>

      {/* Send log */}
      <Card>
        <CardHeader>
          <CardTitle>{t("log")}</CardTitle>
        </CardHeader>
        <CardContent>
          {!log.data || log.data.length === 0 ? (
            <p className="text-sm text-muted">{t("logEmpty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[28rem] text-left text-sm">
                <thead className="text-xs text-muted">
                  <tr>
                    <th className="py-2 pr-4 font-medium">{t("time")}</th>
                    <th className="py-2 pr-4 font-medium">{t("channel")}</th>
                    <th className="py-2 pr-4 font-medium">{t("language")}</th>
                    <th className="py-2 pr-4 font-medium">{t("to")}</th>
                    <th className="py-2 font-medium">{t("status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {log.data.map((r) => (
                    <tr key={r.id} className="border-t">
                      <td className="py-2 pr-4 font-mono text-xs">
                        {format.dateTime(new Date(r.sent_at), { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}
                      </td>
                      <td className="py-2 pr-4">{t(r.channel)}</td>
                      <td className="py-2 pr-4">{localeNames[r.language]}</td>
                      <td className="py-2 pr-4">{r.recipients}</td>
                      <td className="py-2">
                        <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-xs font-semibold text-success">
                          <CheckCircle2 className="h-3 w-3" aria-hidden /> {t("delivered")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
