"use client";

import QRCode from "qrcode";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

/** Theme token ("--qr-fg") -> "#rrggbb" (the QR library only accepts hex). */
function tokenHex(token: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(token).trim().split(/\s+/).map(Number);
  if (v.length < 3 || v.some(Number.isNaN)) return token === "--qr-bg" ? "#ffffff" : "#000000";
  return `#${v
    .slice(0, 3)
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("")}`;
}

/** QR code as inline SVG. Colours come from the --qr-fg / --qr-bg theme tokens. */
export function QrCode({ value, size = 148, className }: { value: string; size?: number; className?: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    QRCode.toString(value, {
      type: "svg",
      margin: 1,
      errorCorrectionLevel: "M",
      color: { dark: tokenHex("--qr-fg"), light: tokenHex("--qr-bg") },
    }).then((s) => !cancelled && setSvg(s));
    return () => {
      cancelled = true;
    };
  }, [value]);
  return (
    <div
      role="img"
      aria-label={value}
      className={cn("overflow-hidden rounded-lg bg-qr-bg p-1.5", className)}
      style={{ width: size, height: size }}
      // SVG generated locally by the qrcode library from `value`
      dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
    />
  );
}
