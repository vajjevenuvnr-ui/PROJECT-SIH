// IMD terminology and colour scales shared by maps, legends and charts.
// Colours reference theme tokens in src/styles/theme.css.

export type RainCategory = {
  key: string;
  label: string;
  min: number; // mm/day, inclusive
  token: string; // CSS variable name
};

/** IMD daily rainfall categories (mm/day). */
export const RAIN_CATEGORIES: RainCategory[] = [
  { key: "none", label: "No rain", min: 0, token: "--rain-0" },
  { key: "very_light", label: "Very light", min: 0.1, token: "--rain-1" },
  { key: "light", label: "Light", min: 2.5, token: "--rain-2" },
  { key: "moderate", label: "Moderate", min: 15.6, token: "--rain-3" },
  { key: "heavy", label: "Heavy", min: 64.5, token: "--rain-4" },
  { key: "very_heavy", label: "Very heavy +", min: 115.6, token: "--rain-5" },
];

export function rainCategory(mm: number): RainCategory {
  let cat = RAIN_CATEGORIES[0];
  for (const c of RAIN_CATEGORIES) if (mm >= c.min) cat = c;
  return cat;
}

export const TEMP_TOKENS = ["--temp-1", "--temp-2", "--temp-3", "--temp-4", "--temp-5"];

/** `rgb(var(--token))` string usable in inline styles, SVG fills and Leaflet. */
export const tokenColor = (token: string) => `rgb(var(${token}))`;
