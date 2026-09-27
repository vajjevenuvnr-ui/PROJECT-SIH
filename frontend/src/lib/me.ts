"use client";

import useSWR from "swr";

import { useDemo } from "@/components/providers/AppProviders";
import { api } from "@/lib/api";

export interface Me {
  id: string | null;
  name: string;
  role: "officer" | "admin";
  is_demo: boolean;
  block_ids: number[] | null;
}

/** The signed-in officer (name, role, assigned blocks). Always asks the live backend with the officer's token,
 *  even when the Demo data switch is on; the built-in demo session has no account. */
export function useMe(): Me | undefined {
  const { demoSession } = useDemo();
  return useSWR<Me>(demoSession ? null : "me", () => api<Me>("/api/me", { demo: false }), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  }).data;
}
