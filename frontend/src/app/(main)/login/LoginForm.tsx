"use client";

import { AlertCircle, Eye, EyeOff, Loader2, PlayCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { DEMO_SELECTION } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { endDemoSession, isSupabaseConfigured, startDemoSession } from "@/lib/session";
import { getSupabaseBrowser } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

const inputCls =
  "h-11 w-full rounded-xl border bg-surface px-3 text-sm outline-none transition-colors placeholder:text-muted focus-visible:border-primary aria-[invalid=true]:border-danger";

function safeNext(next: string | null) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function LoginForm() {
  const t = useTranslations("login");
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"signin" | "demo" | null>(null);
  const configured = isSupabaseConfigured();

  const signIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) return setError(t("errRequired"));
    const sb = getSupabaseBrowser();
    if (!sb) return setError(t("errNotConfigured"));
    setBusy("signin");
    try {
      const { error: err } = await sb.auth.signInWithPassword({ email: email.trim(), password });
      if (err) {
        setError(/invalid/i.test(err.message) ? t("errInvalid") : t("errGeneric"));
        setBusy(null);
        return;
      }
      endDemoSession();
      router.replace(safeNext(params.get("next")));
      router.refresh();
    } catch {
      setError(t("errGeneric"));
      setBusy(null);
    }
  };

  const demo = () => {
    setBusy("demo");
    startDemoSession();
    try {
      localStorage.setItem("pc-region", JSON.stringify(DEMO_SELECTION));
    } catch {}
    router.replace(safeNext(params.get("next")));
    router.refresh();
  };

  return (
    <div className="mt-8 flex flex-col gap-5">
      <form onSubmit={signIn} noValidate className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="email" className="text-sm font-medium">
            {t("email")}
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            placeholder={t("emailPlaceholder")}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={!!error}
            className={inputCls}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="password" className="text-sm font-medium">
            {t("password")}
          </label>
          <div className="relative">
            <input
              id="password"
              type={show ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={!!error}
              className={cn(inputCls, "pr-11")}
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              aria-label={show ? t("hidePassword") : t("showPassword")}
              className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-muted hover:text-foreground"
            >
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {(error || !configured) && (
          <p
            role={error ? "alert" : undefined}
            className={cn(
              "flex items-start gap-2 rounded-xl px-3 py-2.5 text-sm",
              error ? "bg-danger/10 text-danger" : "bg-surface-2 text-muted",
            )}
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            {error ?? t("errNotConfigured")}
          </p>
        )}

        <Button type="submit" size="lg" disabled={busy !== null} className="w-full">
          {busy === "signin" ? (
            <>
              <Loader2 className="animate-spin" /> {t("signingIn")}
            </>
          ) : (
            t("signIn")
          )}
        </Button>
      </form>

      <div className="flex items-center gap-3 text-xs text-muted">
        <span className="h-px flex-1 bg-border" />
        {t("or")}
        <span className="h-px flex-1 bg-border" />
      </div>

      <div className="flex flex-col gap-2">
        <Button type="button" variant="secondary" size="lg" onClick={demo} disabled={busy !== null} className="w-full">
          {busy === "demo" ? <Loader2 className="animate-spin" /> : <PlayCircle className="text-accent" />}
          {t("demo")}
        </Button>
        <p className="text-center text-xs text-muted">{t("demoHint")}</p>
        <details className="rounded-lg border bg-surface px-3 py-2 text-sm">
          <summary className="cursor-pointer font-semibold text-primary">{t("farmerQ")}</summary>
          <p className="mt-2 text-muted">{t("farmerA")}</p>
          <a href="/f/7?lang=te" className="mt-2 inline-block font-semibold text-primary hover:underline">
            {t("farmerLink")} →
          </a>
        </details>
      </div>
    </div>
  );
}
