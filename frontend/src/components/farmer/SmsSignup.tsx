"use client";

import { MessageSquareText } from "lucide-react";
import { useEffect, useState } from "react";

type Labels = {
  title: string;
  body: string;
  mobile: string;
  name: string;
  consent: string;
  submit: string;
  done: string;
  invalid: string;
  error: string;
  stop: string;
  stopped: string;
};

/** Farmer joins the panchayat's SMS / WhatsApp list: mobile + explicit consent, no login. */
export function SmsSignup({ panchayatId, lang, labels }: { panchayatId: number; lang: string; labels: Labels }) {
  const key = `pc-sms-${panchayatId}`;
  const [mobile, setMobile] = useState("");
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState<"idle" | "sending" | "done" | "stopped">("idle");
  const [masked, setMasked] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        setMasked(saved);
        setState("done");
      }
    } catch {}
  }, [key]);

  const digits = mobile.replace(/\D/g, "").replace(/^(91|0)(?=\d{10}$)/, "");
  const valid = /^[6-9]\d{9}$/.test(digits);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return setError(labels.invalid);
    setState("sending");
    setError(null);
    try {
      const res = await fetch("/api/farmers/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ panchayat_id: panchayatId, mobile: digits, name: name || null, language: lang, consent }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const d = (await res.json()) as { mobile_masked: string };
      setMasked(d.mobile_masked);
      try {
        localStorage.setItem(key, d.mobile_masked);
      } catch {}
      setState("done");
    } catch {
      setError(labels.error);
      setState("idle");
    }
  };

  const stop = async () => {
    // Needs the full number again: we never keep it on the device.
    const n = window.prompt(labels.mobile);
    if (!n) return;
    await fetch("/api/farmers/unsubscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ panchayat_id: panchayatId, mobile: n }),
    }).catch(() => null);
    try {
      localStorage.removeItem(key);
    } catch {}
    setState("stopped");
  };

  return (
    <section className="rounded-3xl border bg-surface p-5 shadow-card">
      <p className="flex items-center justify-center gap-2 text-center text-lg font-bold">
        <MessageSquareText className="h-5 w-5 text-primary" aria-hidden /> {labels.title}
      </p>
      {state === "done" ? (
        <div className="mt-3 text-center">
          <p role="status" className="font-semibold text-success">
            {labels.done.replace("{mobile}", masked)}
          </p>
          <button type="button" onClick={stop} className="mt-2 text-sm text-muted underline">
            {labels.stop}
          </button>
        </div>
      ) : state === "stopped" ? (
        <p role="status" className="mt-3 text-center font-semibold text-muted">
          {labels.stopped}
        </p>
      ) : (
        <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
          <p className="text-center text-sm text-muted">{labels.body}</p>
          <label className="text-sm font-semibold">
            {labels.mobile}
            <input
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              maxLength={14}
              value={mobile}
              onChange={(e) => setMobile(e.target.value)}
              placeholder="98765 43210"
              className="mt-1 block h-12 w-full rounded-xl border bg-background px-3 text-lg tracking-wide"
            />
          </label>
          <label className="text-sm font-semibold">
            {labels.name}
            <input
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block h-11 w-full rounded-xl border bg-background px-3"
            />
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-1 h-5 w-5 shrink-0 accent-primary"
            />
            <span>{labels.consent}</span>
          </label>
          {error && (
            <p role="alert" className="text-sm font-semibold text-danger">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={!consent || state === "sending"}
            className="h-14 rounded-2xl bg-primary text-lg font-bold text-primary-foreground disabled:opacity-50"
          >
            {labels.submit}
          </button>
        </form>
      )}
    </section>
  );
}
