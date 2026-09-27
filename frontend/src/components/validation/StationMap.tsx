"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";

import { BASEMAP_ATTRIBUTION, basemapUrl } from "@/components/map/basemap";
import { cssColor, useTheme } from "@/components/theme/useTheme";
import type { ValidationStation } from "@/lib/types";

const GAJWEL: [number, number] = [17.85, 78.66];

function Fit({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [30, 30] });
  }, [map, points]);
  return null;
}

/** Validation stations coloured by whether Kshetra's error is lower (green) or higher (red). */
export default function StationMap({
  stations,
  metric,
  selected,
  onSelect,
  labels,
}: {
  stations: ValidationStation[];
  metric: "tmax" | "rain";
  selected: string | number | null;
  onSelect: (id: string | number) => void;
  labels: { gajwel: string; distance: (km: number) => string; block: string; ours: string };
}) {
  const theme = useTheme();
  const [colors, setColors] = useState({ better: "", worse: "", neutral: "", primary: "", fg: "" });
  useEffect(() => {
    setColors({
      better: cssColor("--color-success"),
      worse: cssColor("--color-danger"),
      neutral: cssColor("--color-muted"),
      primary: cssColor("--color-primary"),
      fg: cssColor("--color-foreground"),
    });
  }, [theme]);
  const points = useMemo(() => [GAJWEL, ...stations.map((s) => [s.lat, s.lon] as [number, number])], [stations]);

  return (
    <MapContainer center={GAJWEL} zoom={8} scrollWheelZoom={false} className="h-full w-full rounded-xl">
      <TileLayer key={theme} url={basemapUrl(theme)} attribution={BASEMAP_ATTRIBUTION} maxZoom={16} />
      <CircleMarker center={GAJWEL} radius={9} pathOptions={{ color: colors.primary, fillColor: colors.primary, fillOpacity: 0.35, weight: 2, dashArray: "4 3" }}>
        <Tooltip direction="top" className="pc-tooltip" permanent>
          {labels.gajwel}
        </Tooltip>
      </CircleMarker>
      {stations.map((s) => {
        const base = metric === "tmax" ? s.tmax_rmse_block : s.rain_mae_block;
        const ours = metric === "tmax" ? s.tmax_rmse_ours : s.rain_mae_ours;
        const tone = base == null || ours == null ? colors.neutral : ours < base - 0.01 ? colors.better : ours > base + 0.01 ? colors.worse : colors.neutral;
        const isSel = s.id === selected;
        return (
          <CircleMarker
            key={String(s.id)}
            center={[s.lat, s.lon]}
            radius={isSel ? 12 : 9}
            pathOptions={{ color: isSel ? colors.fg : tone, fillColor: tone, fillOpacity: 0.85, weight: isSel ? 3 : 1.5 }}
            eventHandlers={{ click: () => onSelect(s.id) }}
          >
            <Tooltip direction="top" className="pc-tooltip">
              <div className="text-xs font-normal">
                <b>{s.name}</b>
                {s.distance_km != null && <div>{labels.distance(s.distance_km)}</div>}
                {base != null && ours != null && (
                  <div>
                    {labels.block}: {base} · {labels.ours}: {ours}
                  </div>
                )}
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
      <Fit points={points} />
    </MapContainer>
  );
}
