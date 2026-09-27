import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";

import { LOCALE_COOKIE, defaultLocale, isLocale } from "./config";

// Locale comes from a cookie (no /en /te URL prefixes), set by the language switch.
// The farmer page (/f/[id]?lang=) picks its own language with createTranslator instead.
export default getRequestConfig(async () => {
  const value = cookies().get(LOCALE_COOKIE)?.value;
  const locale = isLocale(value) ? value : defaultLocale;
  return {
    locale,
    timeZone: "Asia/Kolkata",
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
