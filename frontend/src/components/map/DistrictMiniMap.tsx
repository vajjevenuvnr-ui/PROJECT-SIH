"use client";

import "leaflet/dist/leaflet.css";

import L, { type PathOptions } from "leaflet";
import { useEffect, useMemo } from "react";
import { GeoJSON, MapContainer, Pane, TileLayer, useMap } from "react-leaflet";

import { BASEMAP_ATTRIBUTION, LABELS_PANE, basemapUrl, labelsUrl } from "@/components/map/basemap";
import { cssColor, useTheme } from "@/components/theme/useTheme";
import type { DistrictFeatureProps, FeatureCollection } from "@/lib/types";

interface Props {
  data: FeatureCollection<DistrictFeatureProps>;
  selectedBlockId: number | null;
  onSelectBlock: (id: number) => void;
  nameOf: (p: DistrictFeatureProps) => string;
}

function FitBounds({ data }: { data: Props["data"] }) {
  const map = useMap();
  useEffect(() => {
    const b = L.geoJSON(data as unknown as GeoJSON.GeoJsonObject).getBounds();
    if (b.isValid()) map.fitBounds(b, { padding: [12, 12] });
  }, [data, map]);
  return null;
}

/** S1 mini map: district outline with block outlines; selected block filled in primary. */
export default function DistrictMiniMap({ data, selectedBlockId, onSelectBlock, nameOf }: Props) {
  const theme = useTheme();

  // Colours resolved from theme tokens (Leaflet can't read CSS variables).
  const colors = useMemo(
    () => ({
      primary: cssColor("--color-primary"),
      foreground: cssColor("--color-foreground"),
      accent: cssColor("--color-accent"),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme],
  );

  const style = (f?: GeoJSON.Feature): PathOptions => {
    const p = f?.properties as DistrictFeatureProps;
    if (p.kind === "district") {
      return { color: colors.foreground, weight: 2.5, opacity: 0.55, fill: false, interactive: false };
    }
    const selected = p.id === selectedBlockId;
    return {
      color: colors.primary,
      weight: selected ? 3 : 1.2,
      opacity: selected ? 1 : 0.7,
      fillColor: colors.primary,
      fillOpacity: selected ? 0.55 : 0.06,
    };
  };

  return (
    <MapContainer
      center={[18, 78.85]}
      zoom={9}
      scrollWheelZoom={false}
      attributionControl
      className="h-full w-full rounded-xl"
      style={{ background: "transparent" }}
    >
      <TileLayer key={theme} url={basemapUrl(theme)} attribution={BASEMAP_ATTRIBUTION} maxZoom={16} />
      <Pane name={LABELS_PANE} style={{ zIndex: 650, pointerEvents: "none" }}>
        <TileLayer key={`l-${theme}`} url={labelsUrl(theme)} maxZoom={16} />
      </Pane>
      <GeoJSON
        key={`${theme}-${selectedBlockId}`}
        data={data as unknown as GeoJSON.GeoJsonObject}
        style={style}
        onEachFeature={(f, layer) => {
          const p = f.properties as DistrictFeatureProps;
          if (p.kind !== "block") return;
          layer.bindTooltip(nameOf(p), { sticky: true, direction: "top", className: "pc-tooltip" });
          layer.on({
            click: () => onSelectBlock(p.id),
            mouseover: (e) => {
              if (p.id !== selectedBlockId) (e.target as L.Path).setStyle({ fillOpacity: 0.22 });
            },
            mouseout: (e) => {
              if (p.id !== selectedBlockId) (e.target as L.Path).setStyle({ fillOpacity: 0.06 });
            },
          });
        }}
      />
      <FitBounds data={data} />
    </MapContainer>
  );
}
