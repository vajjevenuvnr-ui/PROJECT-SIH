"use client";

import { BellRing, CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

type State = "checking" | "unsupported" | "insecure" | "disabled" | "idle" | "busy" | "on" | "blocked";

/** Opt this phone in to Web Push extreme-weather alerts for the panchayat (no login). */
export function GetAlertsButton({
  panchayatId,
  lang,
  labels,
}: {
  panchayatId: number;
  lang: string;
  labels: { get: string; on: string; blocked: string; needHttps: string };
}) {
  const [state, setState] = useState<State>("checking");
  const [key, setKey] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      if (!window.isSecureContext) return setState("insecure");
      if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
        return setState("unsupported");
      }
      if (Notification.permission === "denied") return setState("blocked");
      try {
        const res = await fetch("/api/push/public-key");
        const j = await res.json();
        if (!j.enabled || !j.key) return setState("disabled");
        setKey(j.key);
        const reg = await navigator.serviceWorker.getRegistration("/f/");
        const sub = await reg?.pushManager.getSubscription();
        setState(sub && Notification.permission === "granted" ? "on" : "idle");
      } catch {
        setState("disabled");
      }
    })();
  }, []);

  const subscribe = async () => {
    if (!key) return;
    setState("busy");
    try {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") return setState(perm === "denied" ? "blocked" : "idle");
      const reg = (await navigator.serviceWorker.getRegistration("/f/")) ?? (await navigator.serviceWorker.register("/sw.js", { scope: "/f/" }));
      await navigator.serviceWorker.ready;
      const sub =
        (await reg.pushManager.getSubscription()) ??
        (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) }));
      const res = await fetch("/api/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ panchayat_id: panchayatId, lang, subscription: sub.toJSON() }),
      });
      setState(res.ok ? "on" : "idle");
    } catch {
      setState("idle");
    }
  };

  if (state === "checking" || state === "unsupported" || state === "disabled") return null;
  if (state === "insecure") return <p className="text-center text-xs text-muted">{labels.needHttps}</p>;
  if (state === "blocked") return <p className="text-center text-xs text-muted">{labels.blocked}</p>;
  if (state === "on") {
    return (
      <p className="flex items-center justify-center gap-2 rounded-2xl bg-success/10 px-4 py-3 text-sm font-semibold text-success">
        <CheckCircle2 className="h-5 w-5" aria-hidden /> {labels.on}
      </p>
    );
  }
  return (
    <button
      type="button"
      onClick={subscribe}
      disabled={state === "busy"}
      className="flex h-14 w-full items-center justify-center gap-2 rounded-2xl border-2 border-danger bg-surface text-base font-bold text-danger shadow-card disabled:opacity-60"
    >
      {state === "busy" ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> : <BellRing className="h-5 w-5" aria-hidden />}
      {labels.get}
    </button>
  );
}
