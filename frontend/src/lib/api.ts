"use client";

import { getAccessToken } from "@/lib/supabase/client";

// Empty = same origin: /api/* is proxied to FastAPI by next.config.mjs (works on phones over Wi-Fi).
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

// --- Data status ("Cached data" chip) ------------------------------------
type StatusListener = (s: { stale: boolean; source: string | null }) => void;
const listeners = new Set<StatusListener>();

export function onDataStatus(fn: StatusListener) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

function report(res: Response) {
  const s = { stale: res.headers.get("X-Data-Stale") === "1", source: res.headers.get("X-Data-Source") };
  listeners.forEach((fn) => fn(s));
}

// --- Requests --------------------------------------------------------------
export interface ApiOptions {
  demo: boolean;
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

export async function api<T>(path: string, { demo, method = "GET", body, signal }: ApiOptions): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (demo) headers["X-Demo-Mode"] = "1";
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (!demo) {
    const token = await getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Network error: the API is unreachable", 0);
  }
  report(res);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {}
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}
