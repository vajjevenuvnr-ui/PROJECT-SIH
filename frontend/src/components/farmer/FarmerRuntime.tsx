"use client";

import { WifiOff } from "lucide-react";
import { useEffect, useState } from "react";

/** Registers the offline service worker and shows a banner when the phone is offline. */
export function FarmerRuntime({ offlineText }: { offlineText: string }) {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js", { scope: "/f/" }).catch(() => {});
    }
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  if (!offline) return null;
  return (
    <p role="status" className="flex items-center gap-2 rounded-2xl bg-accent/20 px-4 py-3 text-sm font-semibold">
      <WifiOff className="h-4 w-4 shrink-0 text-warning" aria-hidden /> {offlineText}
    </p>
  );
}
