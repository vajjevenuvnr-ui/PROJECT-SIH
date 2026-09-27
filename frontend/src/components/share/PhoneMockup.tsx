"use client";

import { ArrowLeft, BatteryFull, CheckCheck, MessageSquareText, Signal, Wifi } from "lucide-react";
import { Fragment } from "react";

import { cn } from "@/lib/utils";

/** Render WhatsApp-style *bold* and _italic_ as React elements (no HTML injection). */
function RichText({ text, rich }: { text: string; rich: boolean }) {
  if (!rich) return <>{text}</>;
  const tokens = text.split(/(\*[^*\n]+\*|_[^_\n]+_)/g);
  return (
    <>
      {tokens.map((tok, i) => {
        if (tok.startsWith("*") && tok.endsWith("*") && tok.length > 2) return <b key={i}>{tok.slice(1, -1)}</b>;
        if (tok.startsWith("_") && tok.endsWith("_") && tok.length > 2) return <i key={i}>{tok.slice(1, -1)}</i>;
        return <Fragment key={i}>{tok}</Fragment>;
      })}
    </>
  );
}

interface Props {
  channel: "sms" | "whatsapp";
  sender: string;
  /** Messages already "received" on the phone (newest last). */
  messages: { id: string | number; text: string; time: string }[];
  typing: boolean;
  dayLabel: string;
  lang: string;
}

/** CSS-only phone showing what the farmer receives. Colours come from theme tokens. */
export function PhoneMockup({ channel, sender, messages, typing, dayLabel, lang }: Props) {
  const rich = channel === "whatsapp";
  return (
    <div className="mx-auto w-full max-w-[300px]">
      <div className="rounded-[2.6rem] border-[10px] border-foreground/90 bg-foreground/90 shadow-card">
        <div className="relative flex h-[560px] flex-col overflow-hidden rounded-[1.9rem] bg-background">
          {/* notch + status bar */}
          <div className="absolute left-1/2 top-1.5 z-10 h-5 w-24 -translate-x-1/2 rounded-full bg-foreground/90" aria-hidden />
          <div className="flex items-center justify-between px-5 pb-1 pt-2 text-[11px] font-semibold">
            <span>9:41</span>
            <span className="flex items-center gap-1" aria-hidden>
              <Signal className="h-3 w-3" /> <Wifi className="h-3 w-3" /> <BatteryFull className="h-3.5 w-3.5" />
            </span>
          </div>

          {/* chat header */}
          <div className={cn("flex items-center gap-2 px-3 py-2", rich ? "bg-primary text-primary-foreground" : "border-b bg-surface")}>
            <ArrowLeft className="h-4 w-4 opacity-80" aria-hidden />
            <span
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold",
                rich ? "bg-primary-foreground/20" : "bg-primary text-primary-foreground",
              )}
              aria-hidden
            >
              PC
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{sender}</p>
              <p className="text-[10px] opacity-75">{rich ? "WhatsApp" : "SMS"}</p>
            </div>
          </div>

          {/* messages */}
          <div className="flex flex-1 flex-col gap-2 overflow-y-auto bg-surface-2 px-3 py-3" lang={lang}>
            <span className="self-center rounded-full bg-surface px-2.5 py-0.5 text-[10px] text-muted shadow-sm">{dayLabel}</span>
            {messages.length === 0 && !typing && (
              <div className="m-auto flex flex-col items-center gap-2 text-center text-xs text-muted">
                <MessageSquareText className="h-8 w-8 opacity-50" aria-hidden />
              </div>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className="animate-fade-up max-w-[88%] self-start whitespace-pre-wrap break-words rounded-2xl rounded-tl-sm bg-surface px-3 py-2 text-[12.5px] leading-snug shadow-sm"
              >
                <RichText text={m.text} rich={rich} />
                <span className="mt-1 flex items-center justify-end gap-1 text-[10px] text-muted">
                  {m.time}
                  {rich && <CheckCheck className="h-3 w-3 text-info" aria-hidden />}
                </span>
              </div>
            ))}
            {typing && (
              <div className="flex gap-1 self-start rounded-2xl bg-surface px-3 py-3 shadow-sm" aria-hidden>
                {[0, 150, 300].map((d) => (
                  <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted" style={{ animationDelay: `${d}ms` }} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
