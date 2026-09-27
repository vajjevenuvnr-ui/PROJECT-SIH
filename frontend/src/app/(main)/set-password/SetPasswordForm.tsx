"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { endDemoSession } from "@/lib/session";
import { getSupabaseBrowser } from "@/lib/supabase/client";

const inputCls =
  "h-11 w-full rounded-lg border bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25";

/** Reads the invite tokens from the link (#access_token=...&refresh_token=...), starts the session,
 *  then lets the officer set their password. */
export function SetPasswordForm() {
  const t = useTranslations("setPassword");
  const router = useRouter();
  const [state, setState] = useState<"checking" | "ready" | "invalid" | "saving" | "done">("checking");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const sb = getSupabaseBrowser();
    if (!sb) return setState("invalid");
    const hash = new URLSearchParams(window.location.hash.slice(1));
    const access_token = hash.get("access_token");
    const refresh_token = hash.get("refresh_token");
    const start = async () => {
      if (access_token && refresh_token) {
        const { error: e } = await sb.auth.setSession({ access_token, refresh_token });
        window.history.replaceState(null, "", window.location.pathname); // keep tokens out of history
        if (e) return setState("invalid");
      }
      const { data } = await sb.auth.getUser();
      if (!data.user) return setState("invalid");
      setEmail(data.user.email ?? "");
      endDemoSession();
      setState("ready");
    };
    void start();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pw.length < 8) return setError(t("tooShort"));
    if (pw !== pw2) return setError(t("mismatch"));
    setError(null);
    setState("saving");
    const { error: err } = await getSupabaseBrowser()!.auth.updateUser({ password: pw });
    if (err) {
      setError(err.message);
      setState("ready");
      return;
    }
    setState("done");
    setTimeout(() => {
      router.replace("/");
      router.refresh();
    }, 1200);
  };

  if (state === "checking") return <Loader2 className="mt-8 h-6 w-6 animate-spin text-muted" />;
  if (state === "invalid")
    return (
      <p className="mt-6 flex items-start gap-2 rounded-lg bg-danger/10 p-3 text-sm text-danger">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {t("invalid")}
      </p>
    );
  if (state === "done")
    return (
      <p className="mt-6 flex items-center gap-2 font-semibold text-success">
        <CheckCircle2 className="h-5 w-5" /> {t("done")}
      </p>
    );

  return (
    <form onSubmit={submit} className="mt-6 flex flex-col gap-4" noValidate>
      <p className="rounded-lg bg-surface-2 px-3 py-2 text-sm">{email}</p>
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        {t("password")}
        <input type="password" autoComplete="new-password" value={pw} onChange={(e) => (setPw(e.target.value), setError(null))} className={inputCls} />
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        {t("confirm")}
        <input type="password" autoComplete="new-password" value={pw2} onChange={(e) => (setPw2(e.target.value), setError(null))} className={inputCls} />
      </label>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button type="submit" disabled={state === "saving"}>
        {state === "saving" && <Loader2 className="animate-spin" />} {t("save")}
      </Button>
    </form>
  );
}
