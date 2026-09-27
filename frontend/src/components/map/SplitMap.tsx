"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Pane, TileLayer } from "react-leaflet";

import { BASEMAP_ATTRIBUTION, basemapUrl } from "@/components/map/basemap";
import { cssColor, useTheme } from "@/components/theme/useTheme";
import { makeColorScale, readableOn, type Domain } from "@/lib/scales";
import type { AlertLevel, Confidence, ForecastBundle, GpBundleProps, GpDay, Variable } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface SplitMapLabels {
  blockCaption: string;
  gpCaption: string;
  uniform: string;
  range: string;
  chance10: string;
  vsBlock: string;
  elevation: string;
  confidence: Record<Confidence, string>;
  rainCategory: (mm: number) => string;
}

interface Props {
  bundle: ForecastBundle;
  variable: Variable;
  day: number;
  domain: Domain;
  /** Mobile only: which map is visible. */
  mobileView: "block" | "panchayat";
  projector: boolean;
  nameOf: (p: Pick<GpBundleProps, "name" | "name_te" | "name_hi">) => string;
  formatValue: (v: number | null | undefined, variable: Variable) => string;
  labels: SplitMapLabels;
  onOpenPanchayat: (id: number) => void;
  /** Panchayat id -> IMD warning level for the shown day (Orange/Red pulse on the map). */
  alertLevels?: Record<number, AlertLevel>;
}

const LABEL_ZOOM = 12;
const GP_LABELS_PANE = "pc-gp-labels";

const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);

function dayOf(p: GpBundleProps, day: number): GpDay | undefined {
  return p.days.find((d) => d.day === day);
}

function valueOf(d: GpDay | undefined, variable: Variable): number | null {
  if (!d) return null;
  return d[variable] as number | null;
}

/**
 * S2 hero: left = IMD block forecast (one flat colour), right = panchayat choropleth.
 * Both maps share the same colour scale and are synced on pan/zoom.
 * Layers are created once and restyled in place, so colours fade (CSS transition) when the
 * variable or day changes. No basemap place labels here: real village names would clash with the
 * (illustrative) panchayat names; GP names show as our own labels when zoomed in.
 */
export default function SplitMap(props: Props) {
  const { bundle, variable, day, domain, mobileView, projector, labels } = props;
  const theme = useTheme();
  const [left, setLeft] = useState<L.Map | null>(null);
  const [right, setRight] = useState<L.Map | null>(null);

  // Latest props for Leaflet callbacks (which are bound once).
  const live = useRef(props);
  live.current = props;

  const bounds = useMemo(() => {
    const src = bundle.meta?.block_geometry ?? bundle;
    return L.geoJSON(src as unknown as GeoJSON.GeoJsonObject).getBounds();
  }, [bundle]);

  const colorOf = useMemo(
    () => makeColorScale(variable, domain),
    // theme: tokens differ per theme
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [variable, domain, theme],
  );
  const colorRef = useRef(colorOf);
  colorRef.current = colorOf;

  const blockValue = bundle.meta?.block_values.find((b) => b.day === day)?.[variable] ?? null;

  // --- Sync pan/zoom both ways ------------------------------------------------
  useEffect(() => {
    if (!left || !right) return;
    let syncing = false;
    const link = (a: L.Map, b: L.Map) => {
      const handler = () => {
        if (syncing) return;
        syncing = true;
        b.setView(a.getCenter(), a.getZoom(), { animate: false });
        syncing = false;
      };
      a.on("move zoomend", handler);
      return () => a.off("move zoomend", handler);
    };
    const offA = link(left, right);
    const offB = link(right, left);
    return () => {
      offA();
      offB();
    };
  }, [left, right]);

  // Fit both maps to the block on load.
  useEffect(() => {
    if (!bounds.isValid()) return;
    right?.fitBounds(bounds, { padding: [16, 16] });
    left?.fitBounds(bounds, { padding: [16, 16] });
  }, [left, right, bounds]);

  // Resize after mobile toggle / full screen.
  useEffect(() => {
    const id = window.setTimeout(() => {
      left?.invalidateSize();
      right?.invalidateSize();
      if (bounds.isValid()) (mobileView === "block" ? left : right)?.fitBounds(bounds, { padding: [16, 16] });
    }, 80);
    return () => window.clearTimeout(id);
  }, [mobileView, projector, left, right, bounds]);

  // --- Right map: panchayat choropleth -------------------------------------
  const gpLayer = useRef<L.GeoJSON | null>(null);
  const gpLabels = useRef<Map<number, L.Marker>>(new Map());

  useEffect(() => {
    if (!right) return;
    // Borders from the foreground token at low opacity: visible on white "no rain" fills in both themes.
    const border = cssColor("--color-foreground");
    const highlight = cssColor("--color-foreground");
    const fillOpacity = theme === "dark" ? 0.82 : 0.88;

    const style = (f?: GeoJSON.Feature): L.PathOptions => {
      const { variable: v, day: d } = live.current;
      const val = valueOf(dayOf(f!.properties as GpBundleProps, d), v);
      return {
        color: border,
        weight: 1,
        opacity: theme === "dark" ? 0.45 : 0.3,
        fillColor: colorRef.current(val),
        fillOpacity,
        className: "pc-fill",
      };
    };

    const tooltip = (p: GpBundleProps) => {
      const { variable: v, day: d, formatValue, nameOf } = live.current;
      const gd = dayOf(p, d);
      const val = valueOf(gd, v);
      const bv = live.current.bundle.meta?.block_values.find((b) => b.day === d)?.[v] ?? null;
      const diff = val !== null && bv !== null ? Math.round((val - bv) * 10) / 10 : null;
      const local = nameOf(p);
      const second = local !== p.name ? local : p.name_te ?? "";
      const rows: string[] = [];
      if (v === "rain" && gd) {
        rows.push(`<div class="pc-tt-cat">${esc(labels.rainCategory(gd.rain))}</div>`);
        if (gd.rain_min !== null && gd.rain_max !== null)
          rows.push(`<div class="pc-tt-row"><span>${esc(labels.range)}</span><b>${gd.rain_min}–${gd.rain_max} mm</b></div>`);
      }
      if (gd?.rain_prob_10mm != null)
        rows.push(
          `<div class="pc-tt-row"><span>${esc(labels.chance10)}</span><b>${Math.round(gd.rain_prob_10mm * 100)}%</b></div>`,
        );
      if (diff !== null)
        rows.push(
          `<div class="pc-tt-row"><span>${esc(labels.vsBlock)}</span><b>${diff > 0 ? "+" : ""}${esc(formatValue(diff, v))}</b></div>`,
        );
      if (p.elevation_m != null)
        rows.push(`<div class="pc-tt-row"><span>${esc(labels.elevation)}</span><b>${Math.round(p.elevation_m)} m</b></div>`);
      const conf = gd?.confidence ?? "low";
      return `<div class="pc-tt">
        <div class="pc-tt-name">${esc(p.name)}${second ? `<span>${esc(second)}</span>` : ""}</div>
        <div class="pc-tt-value">${esc(formatValue(val, v))}</div>
        ${rows.join("")}
        <span class="pc-pill pc-pill-${conf}">${esc(labels.confidence[conf])}</span>
      </div>`;
    };

    const layer = L.geoJSON(live.current.bundle as unknown as GeoJSON.GeoJsonObject, {
      style,
      onEachFeature: (f, l) => {
        const p = f.properties as GpBundleProps;
        l.bindTooltip(() => tooltip(p), { sticky: true, direction: "top", offset: [0, -10], className: "pc-tooltip" });
        l.on({
          mouseover: (e) => {
            const path = e.target as L.Path;
            path.setStyle({ weight: 3, color: highlight, opacity: 1 });
            path.bringToFront();
          },
          mouseout: (e) => layer.resetStyle(e.target as L.Path),
          click: () => live.current.onOpenPanchayat(p.id),
        });
      },
    }).addTo(right);
    gpLayer.current = layer;

    // Same block outline as the left map, so both show the identical shape.
    const outline = live.current.bundle.meta?.block_geometry
      ? L.geoJSON(live.current.bundle.meta.block_geometry as unknown as GeoJSON.GeoJsonObject, {
          interactive: false,
          style: { fill: false, color: highlight, weight: 2, opacity: theme === "dark" ? 0.7 : 0.55 },
        }).addTo(right)
      : null;

    // Name + value labels at the polygon centres (shown when zoomed in).
    const markers = new Map<number, L.Marker>();
    layer.eachLayer((l) => {
      const poly = l as L.Polygon;
      const p = (poly.feature as GeoJSON.Feature).properties as GpBundleProps;
      const m = L.marker(poly.getCenter(), {
        pane: GP_LABELS_PANE,
        interactive: false,
        keyboard: false,
        icon: L.divIcon({ className: "pc-gp-label-wrap", html: "", iconSize: [0, 0] }),
      }).addTo(right);
      markers.set(p.id, m);
    });
    gpLabels.current = markers;

    const container = right.getContainer();
    const onZoom = () => container.classList.toggle("pc-show-gp-labels", right.getZoom() >= LABEL_ZOOM);
    right.on("zoomend", onZoom);
    onZoom();

    return () => {
      right.off("zoomend", onZoom);
      layer.remove();
      outline?.remove();
      markers.forEach((m) => m.remove());
      gpLayer.current = null;
      gpLabels.current = new Map();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [right, bundle, theme]);

  // Restyle + relabel in place when variable/day/scale changes.
  useEffect(() => {
    const layer = gpLayer.current;
    if (!layer) return;
    layer.eachLayer((l) => {
      layer.resetStyle(l as L.Path);
      // Pulsing outline for Orange/Red warnings (class toggled on the SVG path).
      const id = ((l as L.Polygon).feature as GeoJSON.Feature).properties?.id as number;
      const level = live.current.alertLevels?.[id];
      const el = (l as L.Path).getElement?.();
      el?.classList.toggle("pc-alert-orange", level === "orange");
      el?.classList.toggle("pc-alert-red", level === "red");
      if (level === "orange" || level === "red") (l as L.Path).bringToFront();
    });
    const { formatValue, nameOf } = live.current;
    gpLabels.current.forEach((m, id) => {
      const f = bundle.features.find((x) => x.properties.id === id);
      if (!f) return;
      const val = valueOf(dayOf(f.properties, day), variable);
      m.setIcon(
        L.divIcon({
          className: "pc-gp-label-wrap",
          iconSize: [0, 0],
          html: `<span class="pc-gp-label"><span>${esc(nameOf(f.properties))}</span><b>${esc(formatValue(val, variable))}</b></span>`,
        }),
      );
    });
    // `right`/`theme`: the layer is (re)created in the effect above, so relabel after it exists.
  }, [variable, day, colorOf, bundle, right, theme, props.alertLevels]);

  // --- Left map: flat block value -------------------------------------------
  const blockLayer = useRef<L.GeoJSON | null>(null);
  const blockMarker = useRef<L.Marker | null>(null);

  useEffect(() => {
    if (!left || !bundle.meta?.block_geometry) return;
    const layer = L.geoJSON(bundle.meta.block_geometry as unknown as GeoJSON.GeoJsonObject, {
      style: { color: cssColor("--color-foreground"), weight: 2, opacity: 0.55, fillOpacity: theme === "dark" ? 0.82 : 0.88, className: "pc-fill" },
      interactive: false,
    }).addTo(left);
    const marker = L.marker(layer.getBounds().getCenter(), {
      interactive: false,
      keyboard: false,
      icon: L.divIcon({ className: "pc-block-label-wrap", html: "", iconSize: [0, 0] }),
    }).addTo(left);
    blockLayer.current = layer;
    blockMarker.current = marker;
    return () => {
      layer.remove();
      marker.remove();
      blockLayer.current = null;
      blockMarker.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left, bundle, theme]);

  useEffect(() => {
    const fill = colorOf(blockValue);
    blockLayer.current?.setStyle({ fillColor: fill });
    const { formatValue } = live.current;
    const sub = variable === "rain" && blockValue !== null ? labels.rainCategory(blockValue) : labels.uniform;
    blockMarker.current?.setIcon(
      L.divIcon({
        className: "pc-block-label-wrap",
        iconSize: [0, 0],
        html: `<div class="pc-block-label" style="--pc-label-fg:${readableOn(fill)}"><b>${esc(formatValue(blockValue, variable))}</b><span>${esc(sub)}</span></div>`,
      }),
    );
  }, [blockValue, variable, colorOf, labels, left, bundle, theme]);

  // --- Render ------------------------------------------------------------------
  const panel = (which: "block" | "panchayat") =>
    cn(
      "relative flex min-w-0 flex-col overflow-hidden rounded-card border bg-surface shadow-card",
      mobileView !== which && "hidden md:flex",
    );
  const mapHeight = projector ? "h-full" : "h-[60vh] md:h-[calc(100vh-21rem)] md:min-h-[440px]";

  return (
    <div className={cn("grid gap-3 md:grid-cols-2", projector && "h-full", projector && "pc-projector")}>
      {(["block", "panchayat"] as const).map((which) => (
        <section key={which} className={panel(which)} aria-label={which === "block" ? labels.blockCaption : labels.gpCaption}>
          <header className="flex items-center justify-between gap-2 border-b px-4 py-2.5">
            <h2 className="text-xs font-bold uppercase tracking-wider text-muted">
              {which === "block" ? labels.blockCaption : labels.gpCaption}
            </h2>
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                which === "block" ? "bg-muted" : "bg-primary",
              )}
              aria-hidden
            />
          </header>
          <div className={cn("relative", mapHeight)}>
            <MapContainer
              ref={which === "block" ? setLeft : setRight}
              center={[17.85, 78.68]}
              zoom={11}
              zoomSnap={0.25}
              scrollWheelZoom
              className="h-full w-full"
              attributionControl={which === "panchayat"}
              zoomControl={which === "panchayat"}
            >
              <TileLayer key={`b-${theme}`} url={basemapUrl(theme)} attribution={BASEMAP_ATTRIBUTION} maxZoom={16} />
              <Pane name={GP_LABELS_PANE} style={{ zIndex: 640, pointerEvents: "none" }} />
            </MapContainer>
          </div>
        </section>
      ))}
    </div>
  );
}
