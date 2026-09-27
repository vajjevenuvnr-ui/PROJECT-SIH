"use client";

import { Square, Volume2 } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const VOICE_LANG: Record<string, string[]> = { te: ["te-IN", "te"], hi: ["hi-IN", "hi"], en: ["en-IN", "en-GB", "en-US", "en"] };
const FALLBACK: Record<string, string[]> = { te: ["hi", "en"], hi: ["en"], en: [] };

function pickVoice(lang: string): { voice: SpeechSynthesisVoice | null; used: string } {
  const voices = window.speechSynthesis.getVoices();
  for (const l of [lang, ...(FALLBACK[lang] ?? [])]) {
    const v = voices.find((x) => VOICE_LANG[l]?.some((code) => x.lang.toLowerCase().startsWith(code.toLowerCase())));
    if (v) return { voice: v, used: l };
  }
  return { voice: null, used: lang };
}

/** Reads the advice aloud with the phone's built-in text-to-speech (for low-literacy farmers). */
export function ListenButton({
  text,
  lang,
  labels,
}: {
  text: string;
  lang: string;
  labels: { listen: string; stop: string; noVoice: string; langNames: Record<string, string> };
}) {
  const [supported, setSupported] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!("speechSynthesis" in window)) setSupported(false);
    else window.speechSynthesis.getVoices(); // warm up the voice list (loads async on Android)
    return () => {
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, []);

  const toggle = () => {
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    const { voice, used } = pickVoice(lang);
    const u = new SpeechSynthesisUtterance(text);
    u.lang = VOICE_LANG[used][0];
    if (voice) u.voice = voice;
    u.rate = 0.9;
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    setNote(used !== lang ? labels.noVoice.replace("{lang}", labels.langNames[used] ?? used) : null);
    synth.cancel();
    synth.speak(u);
    setSpeaking(true);
  };

  if (!supported) return null;
  return (
    <div className="flex flex-1 flex-col gap-1">
      <button
        type="button"
        onClick={toggle}
        className={cn(
          "flex h-14 w-full items-center justify-center gap-2 rounded-2xl text-lg font-bold shadow-card transition-colors",
          speaking ? "bg-accent text-accent-foreground" : "bg-primary text-primary-foreground",
        )}
      >
        {speaking ? <Square className="h-5 w-5" aria-hidden /> : <Volume2 className="h-6 w-6" aria-hidden />}
        {speaking ? labels.stop : labels.listen}
      </button>
      {note && <p className="text-center text-xs text-muted">{note}</p>}
    </div>
  );
}
