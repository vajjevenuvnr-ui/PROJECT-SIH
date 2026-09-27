// SMS length rules (mirrors backend/app/services/messages.py so officer edits update the count live).
const GSM7_BASIC = new Set(
  "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡" +
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà",
);
const GSM7_EXT = new Set("^{}\\[~]|€");

export interface SmsInfo {
  encoding: "GSM-7" | "UCS-2";
  chars: number;
  units: number;
  segments: number;
  per_segment: number;
}

export function smsInfo(text: string): SmsInfo {
  const chars = Array.from(text);
  const gsm = chars.every((c) => GSM7_BASIC.has(c) || GSM7_EXT.has(c));
  const units = gsm ? chars.reduce((n, c) => n + (GSM7_EXT.has(c) ? 2 : 1), 0) : text.length; // JS length = UTF-16 units
  const [single, multi] = gsm ? [160, 153] : [70, 67];
  const segments = units <= single ? 1 : Math.ceil(units / multi);
  return { encoding: gsm ? "GSM-7" : "UCS-2", chars: chars.length, units, segments, per_segment: segments === 1 ? single : multi };
}
