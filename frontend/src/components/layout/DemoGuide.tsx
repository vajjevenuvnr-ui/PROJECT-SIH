"use client";

import { Pause, Play, RotateCcw, Timer, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useDemo, useRegion } from "@/components/providers/AppProviders";
import { cn } from "@/lib/utils";

// Demo script (documents/02 and 06): 6 steps, target times in seconds.
const STEPS = [
  { key: "1", label: "S1 Home: open Gajwel", path: () => "/", target: 10 },
  { key: "2", label: "S2 Split map: Rain -> Tmax -> Rain, move day", path: (b: number) => `/block/${b}?var=rain&day=2`, target: 15 },
  { key: "3", label: "S3 Ahmadipur detail", path: () => "/panchayat/7", target: 15 },
  { key: "4", label: "S4 Cotton advisory + Why?", path: () => "/panchayat/7/advisory", target: 15 },
  { key: "5", label: "S5 Share in Telugu", path: () => "/share", target: 15 },
  { key: "6", label: "S6 Validation", path: () => "/validation", target: 15 },
];

/** Presenter helper: Shift+D toggles the guide + stopwatch; keys 1-6 jump to each demo step. */
export function DemoGuide() {
  const router = useRouter();
  const { demo } = useDemo();
  const { selection } = useRegion();
  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [ms, setMs] = useState(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el?.closest("input, textarea, [contenteditable=true]")) return;
      if (e.shiftKey && e.key.toLowerCase() === "d") {
        setOpen((o) => !o);
        return;
      }
      if (!demo || e.ctrlKey || e.metaKey || e.altKey) return;
      const step = STEPS.find((s) => s.key === e.key);
      if (step) router.push(step.path(selection.blockId ?? 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [demo, router, selection.blockId]);

  useEffect(() => {
    if (!running) return;
    const t0 = Date.now() - ms;
    const id = window.setInterval(() => setMs(Date.now() - t0), 200);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  if (!open) return null;
  const secs = ms / 1000;
  const total = STEPS.reduce((a, s) => a + s.target, 0);
  return (
    <div className="fixed bottom-20 right-4 z-[1150] w-80 rounded-card border bg-surface p-4 text-sm shadow-card md:bottom-4">
      <div className="mb-2 flex items-center justify-between">
        <p className="flex items-center gap-2 font-bold">
          <Timer className="h-4 w-4 text-primary" aria-hidden /> Demo guide
        </p>
        <button onClick={() => setOpen(false)} aria-label="Close" className="text-muted hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>
      <p className={cn("text-3xl font-extrabold tabular-nums", secs > 90 ? "text-danger" : secs > 75 ? "text-warning" : "text-foreground")}>
        {Math.floor(secs / 60)}:{String(Math.floor(secs % 60)).padStart(2, "0")}
        <span className="ml-2 text-xs font-semibold text-muted">target &lt; 1:30 ({total}s)</span>
      </p>
      <div className="my-2 flex gap-2">
        <button onClick={() => setRunning((r) => !r)} className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 font-semibold text-primary-foreground">
          {running ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />} {running ? "Pause" : "Start"}
        </button>
        <button onClick={() => { setRunning(false); setMs(0); }} className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 font-semibold">
          <RotateCcw className="h-4 w-4" /> Reset
        </button>
      </div>
      <ol className="flex flex-col gap-1">
        {STEPS.map((s) => (
          <li key={s.key}>
            <button onClick={() => router.push(s.path(selection.blockId ?? 1))} className="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left hover:bg-surface-2">
              <kbd className="rounded border bg-surface-2 px-1.5 text-xs font-bold">{s.key}</kbd>
              <span className="flex-1">{s.label}</span>
              <span className="text-xs text-muted">{s.target}s</span>
            </button>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-xs text-muted">Shift+D hides this. Keys 1-6 jump (Demo Mode only).</p>
    </div>
  );
}
