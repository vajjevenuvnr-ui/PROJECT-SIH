import type { Region } from "@/lib/types";

/** Region/panchayat name in the UI language, falling back to English. */
export function localName(r: Pick<Region, "name" | "name_te" | "name_hi"> | null | undefined, locale: string): string {
  if (!r) return "";
  if (locale === "te" && r.name_te) return r.name_te;
  if (locale === "hi" && r.name_hi) return r.name_hi;
  return r.name;
}
