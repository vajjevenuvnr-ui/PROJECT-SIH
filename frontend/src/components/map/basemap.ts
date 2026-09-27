import type { Theme } from "@/components/theme/useTheme";

// Esri grey canvas basemaps (no API key, muted so data colours stand out):
// a base layer under the polygons and a place-name layer above them.
export const BASEMAP_ATTRIBUTION =
  'Tiles &copy; <a href="https://www.esri.com">Esri</a> &mdash; Esri, HERE, Garmin, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas";

export function basemapUrl(theme: Theme): string {
  const name = theme === "dark" ? "World_Dark_Gray_Base" : "World_Light_Gray_Base";
  return `${ESRI}/${name}/MapServer/tile/{z}/{y}/{x}`;
}

export function labelsUrl(theme: Theme): string {
  const name = theme === "dark" ? "World_Dark_Gray_Reference" : "World_Light_Gray_Reference";
  return `${ESRI}/${name}/MapServer/tile/{z}/{y}/{x}`;
}

/** Leaflet pane for place labels, drawn above data polygons and ignoring the mouse. */
export const LABELS_PANE = "pc-labels";
