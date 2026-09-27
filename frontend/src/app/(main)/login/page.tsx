import { CloudRain, Gauge, Languages } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Suspense } from "react";

import { Logo } from "@/components/brand/Logo";
import { LanguageSwitch } from "@/components/layout/LanguageSwitch";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Sign in" };

/** Decorative contour lines (terrain) for the brand panel. */
function ContourPattern() {
  const rings = [60, 110, 160, 210, 260, 310, 360, 410];
  return (
    <svg
      aria-hidden
      className="pointer-events-none absolute inset-0 h-full w-full text-primary-foreground opacity-[0.09]"
      viewBox="0 0 800 900"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      {rings.map((r, i) => (
        <path
          key={r}
          d={`M ${560 - r} ${260 + i * 6}
              C ${560 - r} ${260 - r * 0.8}, ${560 + r * 1.1} ${260 - r * 0.7}, ${560 + r} ${260 + i * 4}
              S ${560 - r * 0.2} ${260 + r * 1.2}, ${560 - r} ${260 + i * 6} Z`}
        />
      ))}
      {rings.slice(0, 6).map((r, i) => (
        <path
          key={`b${r}`}
          d={`M ${180 - r * 0.7} ${700 + i * 5}
              C ${180 - r * 0.6} ${700 - r * 0.9}, ${180 + r} ${700 - r * 0.6}, ${180 + r * 0.9} ${700 + i * 3}
              S ${180 - r * 0.1} ${700 + r}, ${180 - r * 0.7} ${700 + i * 5} Z`}
        />
      ))}
    </svg>
  );
}

export default async function LoginPage() {
  const t = await getTranslations("login");
  const common = await getTranslations("common");
  const values = [
    { icon: CloudRain, title: t("value1Title"), body: t("value1Body") },
    { icon: Gauge, title: t("value2Title"), body: t("value2Body") },
    { icon: Languages, title: t("value3Title"), body: t("value3Body") },
  ];

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* LEFT: brand panel (collapses to a header band on mobile) */}
      <aside className="relative overflow-hidden bg-primary text-primary-foreground md:flex md:w-[45%] md:flex-col md:justify-between md:p-12 lg:p-16">
        <ContourPattern />
        <div className="relative flex items-center justify-between px-4 py-4 md:block md:p-0">
          <Logo size="md" variant="inverse" className="md:hidden" priority />
          <Logo size="lg" variant="inverse" className="hidden md:inline-flex" priority />
        </div>

        <div className="relative hidden md:block">
          <h1 className="max-w-md text-3xl font-bold leading-tight lg:text-4xl">{common("tagline")}</h1>
          <ul className="mt-10 flex flex-col gap-6">
            {values.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-foreground/15">
                  <Icon className="h-5 w-5" aria-hidden />
                </span>
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="mt-0.5 text-sm opacity-80">{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative hidden text-xs opacity-70 md:block">{t("footer")}</p>
      </aside>

      {/* RIGHT: form */}
      <main className="relative flex flex-1 flex-col bg-surface">
        <div className="flex items-center justify-end gap-2 p-4">
          <LanguageSwitch />
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center px-4 pb-12 sm:px-8">
          <div className="w-full max-w-sm">
            <h2 className="text-2xl font-bold">{t("heading")}</h2>
            <p className="mt-1.5 text-sm text-muted">{t("subheading")}</p>
            <Suspense>
              <LoginForm />
            </Suspense>
          </div>
        </div>
        <p className="px-4 pb-6 text-center text-xs text-muted md:hidden">{t("footer")}</p>
      </main>
    </div>
  );
}
