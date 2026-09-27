"use client";

import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

/** Current theme from <html data-theme>, updated live when ThemeToggle changes it. */
export function useTheme(): Theme {
  const [theme, setTheme] = useState<Theme>("light");
  useEffect(() => {
    const el = document.documentElement;
    const read = () => setTheme(el.getAttribute("data-theme") === "dark" ? "dark" : "light");
    read();
    const obs = new MutationObserver(read);
    obs.observe(el, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);
  return theme;
}

/**
 * Resolve a theme token (e.g. "--color-primary") to a concrete colour string.
 * Needed for Leaflet/SVG attributes, which cannot use CSS var() directly.
 * Call again after the theme changes.
 */
export function cssColor(token: string, alpha = 1): string {
  if (typeof window === "undefined") return "transparent";
  const v = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  if (!v) return "transparent";
  return alpha < 1 ? `rgb(${v} / ${alpha})` : `rgb(${v})`;
}
