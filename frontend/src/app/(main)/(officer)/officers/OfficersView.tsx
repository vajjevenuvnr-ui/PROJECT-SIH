"use client";

import { Check, Copy, Loader2, ShieldCheck, Trash2, UserPlus } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { useState } from "react";

import { useApi } from "@/components/providers/AppProviders";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useMe } from "@/lib/me";
import { localName } from "@/lib/names";
import type { Lang, Region } from "@/lib/types";
import { cn } from "@/lib/utils";

type Officer = {
  id: string;
  email: string;
  name: string | null;
  role: "officer" | "admin";
  block_ids: number[];
  status: "active" | "invited";
  last_sign_in_at: string | null;
  is_you: boolean;
};
type Invite = { email: string; name: string; invite_link: string; expires_hours: number };

const inputCls = "h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none focus:border-primary";

/** Admin only: invite officers by official email, assign blocks, remove. Always uses the live database. */
export function OfficersView() {
  const t = useTranslations("officers");
  const locale = useLocale() as Lang;
  const me = useMe();
  const blocks = useApi<Region[]>("/api/regions/blocks");
  const officers = useSWR<Officer[]>(me?.role === "admin" ? "officers" : null, () =>
    api<Officer[]>("/api/officers", { demo: false }),
  );
  const [form, setForm] = useState({ email: "", name: "", role: "officer" as "officer" | "admin", block_ids: [] as number[] });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [invite, setInvite] = useState<Invite | null>(null);
  const [copied, setCopied] = useState(false);

  if (me === undefined) return <Skeleton className="h-40 w-full" />;
  if (me.role !== "admin") return <p className="text-muted">{t("adminOnly")}</p>;
  if (officers.error) return <ErrorCard message={officers.error.message} onRetry={() => officers.mutate()} />;

  const blockName = (id: number) => {
    const b = blocks.data?.find((x) => x.id === id);
    return b ? localName(b, locale) : `#${id}`;
  };
  const allBlocks = blocks.data ?? [];

  const toggle = (ids: number[], id: number) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id].sort((a, b) => a - b));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("invite");
    setError(null);
    setInvite(null);
    try {
      const r = await api<Invite>("/api/officers/invite", { demo: false, method: "POST", body: form });
      setInvite(r);
      setCopied(false);
      setForm({ email: "", name: "", role: "officer", block_ids: [] });
      await officers.mutate();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const setBlocks = async (o: Officer, ids: number[]) => {
    setBusy(o.id);
    try {
      await api(`/api/officers/${o.id}`, { demo: false, method: "PATCH", body: { block_ids: ids } });
      await officers.mutate();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const remove = async (o: Officer) => {
    if (!window.confirm(t("confirmRemove", { name: o.name ?? o.email }))) return;
    setBusy(o.id);
    try {
      await api(`/api/officers/${o.id}`, { demo: false, method: "DELETE" });
      await officers.mutate();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const copy = async () => {
    if (!invite) return;
    try {
      await navigator.clipboard.writeText(invite.invite_link);
      setCopied(true);
    } catch {}
  };

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">{t("title")}</h1>
        <p className="mt-1 text-muted">{t("subtitle")}</p>
      </div>

      <Card className="p-5">
        <h2 className="flex items-center gap-2 font-bold">
          <UserPlus className="h-4 w-4 text-primary" aria-hidden /> {t("inviteTitle")}
        </h2>
        <form onSubmit={submit} className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium">
            {t("email")}
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="aeo.gajwel@telangana.gov.in"
              className={cn(inputCls, "mt-1")}
            />
          </label>
          <label className="text-sm font-medium">
            {t("name")}
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className={cn(inputCls, "mt-1")}
            />
          </label>
          <label className="text-sm font-medium">
            {t("role")}
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as "officer" | "admin" })}
              className={cn(inputCls, "mt-1")}
            >
              <option value="officer">{t("roleOfficer")}</option>
              <option value="admin">{t("roleAdmin")}</option>
            </select>
          </label>
          <fieldset className="text-sm font-medium sm:col-span-2">
            <legend>{t("blocks")}</legend>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {allBlocks.map((b) => {
                const on = form.block_ids.includes(b.id);
                return (
                  <button
                    key={b.id}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setForm({ ...form, block_ids: toggle(form.block_ids, b.id) })}
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                      on ? "border-primary bg-primary text-primary-foreground" : "hover:bg-surface-2",
                    )}
                  >
                    {localName(b, locale)}
                  </button>
                );
              })}
            </div>
          </fieldset>
          <p className="text-xs text-muted sm:col-span-2">{t("domainHint")}</p>
          {error && <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger sm:col-span-2">{error}</p>}
          <div className="sm:col-span-2">
            <Button type="submit" disabled={busy !== null}>
              {busy === "invite" ? <Loader2 className="animate-spin" /> : <UserPlus />} {t("invite")}
            </Button>
          </div>
        </form>

        {invite && (
          <div className="mt-4 rounded-xl border border-success/40 bg-success/10 p-4 text-sm">
            <p className="font-semibold text-success">{t("invited", { name: invite.name, email: invite.email })}</p>
            <p className="mt-1 text-muted">{t("linkHint", { hours: invite.expires_hours })}</p>
            <div className="mt-2 flex gap-2">
              <input readOnly value={invite.invite_link} className={cn(inputCls, "font-mono text-xs")} aria-label={t("link")} />
              <Button type="button" variant="secondary" onClick={copy}>
                {copied ? <Check /> : <Copy />} {copied ? t("copied") : t("copy")}
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b p-3 text-xs text-muted">
          <ShieldCheck className="h-3.5 w-3.5 text-success" aria-hidden /> {t("signupOff")}
        </div>
        {!officers.data ? (
          <div className="p-4">
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <div className="divide-y">
            {officers.data.map((o) => (
              <div key={o.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">
                    {o.name ?? "–"} {o.is_you && <span className="text-xs text-muted">({t("you")})</span>}
                  </p>
                  <p className="truncate text-sm text-muted">{o.email}</p>
                  <p className="mt-1 flex flex-wrap gap-1.5 text-xs">
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 font-semibold text-primary">
                      {o.role === "admin" ? t("roleAdmin") : t("roleOfficer")}
                    </span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 font-semibold",
                        o.status === "active" ? "bg-success/15 text-success" : "bg-accent/20",
                      )}
                    >
                      {o.status === "active" ? t("active") : t("pending")}
                    </span>
                  </p>
                </div>
                <div className="flex flex-wrap gap-1 sm:max-w-md sm:justify-end">
                  {o.role === "admin" ? (
                    <span className="text-xs text-muted">{t("allBlocks")}</span>
                  ) : (
                    allBlocks.map((b) => {
                      const on = o.block_ids.includes(b.id);
                      return (
                        <button
                          key={b.id}
                          type="button"
                          aria-pressed={on}
                          disabled={busy !== null || (on && o.block_ids.length === 1)}
                          onClick={() => setBlocks(o, toggle(o.block_ids, b.id))}
                          title={blockName(b.id)}
                          className={cn(
                            "rounded-full border px-2 py-0.5 text-[11px] font-semibold transition-colors disabled:opacity-60",
                            on ? "border-primary bg-primary/15 text-primary" : "text-muted hover:bg-surface-2",
                          )}
                        >
                          {localName(b, locale)}
                        </button>
                      );
                    })
                  )}
                </div>
                {!o.is_you && (
                  <Button variant="ghost" size="icon" onClick={() => remove(o)} disabled={busy !== null} aria-label={t("remove")}>
                    {busy === o.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
