"use client";

import { Siren, Volume2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { playSiren, unlockAudio, vibrateAlert } from "@/lib/siren";
import { cn } from "@/lib/utils";

export interface FarmerWarning {
  id: string;
  level: "yellow" | "orange" | "red";
  title: string;
  body: string;
  actions: string[];
  value: number;
  unit: string;
  date: string;
  siren: boolean;
  simulated: boolean;
}

const STYLE = {
  yellow: "bg-alert-yellow text-alert-on-yellow",
  orange: "bg-alert-orange text-alert-on-orange",
  red: "bg-alert-red text-alert-on-red",
};
const SPEECH_LANG: Record<string, string> = { te: "te-IN", hi: "hi-IN", en: "en-IN" };

/**
 * Extreme-weather warning for farmers.
 * - Inline card whenever an Orange/Red (or Yellow) warning is active.
 * - Full-screen SOS view when opened from a push notification (?sos=1).
 * Sound needs a tap (browser rule), so the SOS view has one big "Tap to hear" button.
 */
export function SosAlert({
  warning,
  fullscreen,
  lang,
  dayLabel,
  labels,
}: {
  warning: FarmerWarning;
  fullscreen: boolean;
  lang: string;
  dayLabel: string;
  labels: { title: string; tap: string; doNow: string; close: string; simulated: string };
}) {
  const [open, setOpen] = useState(fullscreen);

  useEffect(() => {
    if (fullscreen) vibrateAlert(); // vibration is allowed without a tap on most Android phones
  }, [fullscreen]);

  const hear = async () => {
    await unlockAudio();
    playSiren(3);
    vibrateAlert();
    if ("speechSynthesis" in window) {
      const u = new SpeechSynthesisUtterance(`${warning.title}. ${warning.body} ${warning.actions.join(". ")}`);
      u.lang = SPEECH_LANG[lang] ?? "te-IN";
      u.rate = 0.9;
      window.setTimeout(() => {
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(u);
      }, 3700); // after the siren
    }
  };

  const close = () => {
    setOpen(false);
    const url = new URL(window.location.href);
    url.searchParams.delete("sos");
    window.history.replaceState(null, "", url.toString());
  };

  const body = (
    <>
      {warning.simulated && (
        <p className="rounded-lg bg-black/20 px-3 py-1.5 text-center text-xs font-bold uppercase tracking-wide">{labels.simulated}</p>
      )}
      <div className="flex items-start gap-3">
        <Siren className={cn("h-10 w-10 shrink-0", warning.level !== "yellow" && "animate-pulse")} aria-hidden />
        <div>
          <p className="text-xs font-bold uppercase tracking-wider opacity-90">{labels.title}</p>
          <p className="text-2xl font-extrabold leading-tight">{warning.title}</p>
          <p className="mt-1 text-lg font-bold">
            {warning.value} {warning.unit} · {dayLabel}
          </p>
        </div>
      </div>
      <div className="rounded-2xl bg-black/15 p-4">
        <p className="mb-2 text-sm font-bold uppercase tracking-wide opacity-90">{labels.doNow}</p>
        <ol className="flex flex-col gap-2">
          {warning.actions.map((a, i) => (
            <li key={i} className="flex gap-3 text-lg font-bold leading-snug">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-black/20 text-base">{i + 1}</span>
              {a}
            </li>
          ))}
        </ol>
      </div>
      <button
        type="button"
        onClick={hear}
        className="flex h-16 w-full items-center justify-center gap-3 rounded-2xl bg-black/25 text-xl font-extrabold"
      >
        <Volume2 className="h-7 w-7" aria-hidden /> {labels.tap}
      </button>
    </>
  );

  if (open) {
    return (
      <div role="alertdialog" aria-modal="true" aria-label={labels.title} className={cn("fixed inset-0 z-50 flex flex-col gap-4 overflow-y-auto p-5", STYLE[warning.level])}>
        <div className="flex justify-end">
          <button type="button" onClick={close} className="inline-flex items-center gap-1 rounded-full bg-black/20 px-4 py-2 text-sm font-bold">
            <X className="h-4 w-4" aria-hidden /> {labels.close}
          </button>
        </div>
        {body}
      </div>
    );
  }
  return (
    <section role="alert" className={cn("flex flex-col gap-3 rounded-3xl p-5 shadow-card", STYLE[warning.level])}>
      {body}
    </section>
  );
}
