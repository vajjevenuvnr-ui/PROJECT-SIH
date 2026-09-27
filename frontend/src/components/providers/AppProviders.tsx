"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import useSWR, { SWRConfig, type SWRConfiguration } from "swr";

import { api, onDataStatus } from "@/lib/api";
import { DEMO_DATA_COOKIE, setClientCookie } from "@/lib/session";

// ---------------------------------------------------------------------------
// Demo Mode
// ---------------------------------------------------------------------------
interface DemoState {
  /** API calls use cached demo data. */
  demo: boolean;
  /** Signed in as the built-in demo officer (demo is then always on). */
  demoSession: boolean;
  setDemo: (on: boolean) => void;
}

const DemoContext = createContext<DemoState | null>(null);

export function useDemo() {
  const ctx = useContext(DemoContext);
  if (!ctx) throw new Error("useDemo must be used inside AppProviders");
  return ctx;
}

// ---------------------------------------------------------------------------
// Selected region (persisted per browser)
// ---------------------------------------------------------------------------
export interface RegionSelection {
  stateId: number | null;
  districtId: number | null;
  blockId: number | null;
}

const EMPTY: RegionSelection = { stateId: null, districtId: null, blockId: null };
// Demo script: Telangana > Siddipet > Gajwel pre-selected.
export const DEMO_SELECTION: RegionSelection = { stateId: 1, districtId: 1, blockId: 1 };
const REGION_KEY = "pc-region";

interface RegionState {
  selection: RegionSelection;
  setSelection: (s: RegionSelection) => void;
  ready: boolean;
}

const RegionContext = createContext<RegionState | null>(null);

export function useRegion() {
  const ctx = useContext(RegionContext);
  if (!ctx) throw new Error("useRegion must be used inside AppProviders");
  return ctx;
}

// ---------------------------------------------------------------------------
// Data status (stale / source), fed by response headers
// ---------------------------------------------------------------------------
const DataStatusContext = createContext<{ stale: boolean; source: string | null }>({ stale: false, source: null });

export function useDataStatus() {
  return useContext(DataStatusContext);
}

// ---------------------------------------------------------------------------
// Data hook: SWR keyed by path + demo flag
// ---------------------------------------------------------------------------
export function useApi<T>(path: string | null, config?: SWRConfiguration<T>) {
  const { demo } = useDemo();
  return useSWR<T>(path ? [path, demo] : null, ([p, d]: [string, boolean]) => api<T>(p, { demo: d }), config);
}

// ---------------------------------------------------------------------------
export function AppProviders({
  children,
  initialDemo,
  demoSession,
}: {
  children: React.ReactNode;
  initialDemo: boolean;
  demoSession: boolean;
}) {
  const [demo, setDemoState] = useState(initialDemo || demoSession);
  const setDemo = useCallback(
    (on: boolean) => {
      if (demoSession) return; // locked on
      setClientCookie(DEMO_DATA_COOKIE, on ? "1" : null);
      setDemoState(on);
    },
    [demoSession],
  );

  const [selection, setSelectionState] = useState<RegionSelection>(EMPTY);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let saved: RegionSelection | null = null;
    try {
      const raw = localStorage.getItem(REGION_KEY);
      if (raw) saved = JSON.parse(raw);
    } catch {}
    setSelectionState(saved?.blockId ? saved : demo ? DEMO_SELECTION : EMPTY);
    setReady(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const setSelection = useCallback((s: RegionSelection) => {
    setSelectionState(s);
    try {
      localStorage.setItem(REGION_KEY, JSON.stringify(s));
    } catch {}
  }, []);

  const [status, setStatus] = useState<{ stale: boolean; source: string | null }>({ stale: false, source: null });
  useEffect(() => onDataStatus(setStatus), []);

  const demoValue = useMemo(() => ({ demo, demoSession, setDemo }), [demo, demoSession, setDemo]);
  const regionValue = useMemo(() => ({ selection, setSelection, ready }), [selection, setSelection, ready]);

  return (
    <SWRConfig value={{ revalidateOnFocus: false, dedupingInterval: 30_000, keepPreviousData: true }}>
      <DemoContext.Provider value={demoValue}>
        <RegionContext.Provider value={regionValue}>
          <DataStatusContext.Provider value={status}>{children}</DataStatusContext.Provider>
        </RegionContext.Provider>
      </DemoContext.Provider>
    </SWRConfig>
  );
}
