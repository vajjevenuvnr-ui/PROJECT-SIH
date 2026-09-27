export const locales = ["en", "te", "hi"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export const localeLabels: Record<Locale, string> = { en: "EN", te: "తె", hi: "हि" };
export const localeNames: Record<Locale, string> = { en: "English", te: "తెలుగు", hi: "हिन्दी" };

export function isLocale(v: string | undefined | null): v is Locale {
  return !!v && (locales as readonly string[]).includes(v);
}
