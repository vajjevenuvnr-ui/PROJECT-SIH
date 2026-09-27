"use client";

import { CloudRain, Sun } from "lucide-react";
import { useEffect, useState } from "react";

/** "Did it rain today?" one-tap feedback. One answer per device per day (stored locally). */
export function RainFeedback({
  panchayatId,
  labels,
}: {
  panchayatId: number;
  labels: { question: string; yes: string; no: string; thanks: string; already: string };
}) {
  const [state, setState] = useState<"idle" | "sending" | "done" | "already">("idle");
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  const key = `pc-rain-${panchayatId}-${today}`;

  useEffect(() => {
    try {
      if (localStorage.getItem(key)) setState("already");
    } catch {}
  }, [key]);

  const answer = async (rained: boolean) => {
    setState("sending");
    try {
      const res = await fetch("/api/feedback/rain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ panchayat_id: panchayatId, rained }),
      });
      if (!res.ok) throw new Error(String(res.status));
      try {
        localStorage.setItem(key, rained ? "yes" : "no");
      } catch {}
      setState("done");
    } catch {
      setState("idle");
    }
  };

  return (
    <section className="rounded-3xl border bg-surface p-5 shadow-card">
      <p className="text-center text-lg font-bold">{labels.question}</p>
      {state === "done" || state === "already" ? (
        <p role="status" className="mt-3 text-center font-semibold text-success">
          {state === "done" ? labels.thanks : labels.already}
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <button
            type="button"
            disabled={state === "sending"}
            onClick={() => answer(true)}
            className="flex h-16 items-center justify-center gap-2 rounded-2xl bg-info text-xl font-bold text-white disabled:opacity-60"
          >
            <CloudRain className="h-6 w-6" aria-hidden /> {labels.yes}
          </button>
          <button
            type="button"
            disabled={state === "sending"}
            onClick={() => answer(false)}
            className="flex h-16 items-center justify-center gap-2 rounded-2xl bg-accent text-xl font-bold text-accent-foreground disabled:opacity-60"
          >
            <Sun className="h-6 w-6" aria-hidden /> {labels.no}
          </button>
        </div>
      )}
    </section>
  );
}
