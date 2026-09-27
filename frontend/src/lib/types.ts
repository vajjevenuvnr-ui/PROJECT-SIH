// Response types mirroring backend/app/schemas/api.py.

export type Variable = "rain" | "tmax" | "tmin" | "rh" | "wind";
export type Confidence = "high" | "medium" | "low";
export type Lang = "en" | "te" | "hi";

export interface Region {
  id: number;
  lgd_code: string;
  name: string;
  name_te?: string | null;
  name_hi?: string | null;
  panchayat_count?: number | null;
}

export interface RunInfo {
  id: number;
  issued_at: string;
  source: string;
  source_label: string;
  status: "ok" | "stale" | "failed" | "running";
  duration_s?: number | null;
}

export interface Alert {
  type: "rain" | "heat" | "wind";
  severity: "watch" | "warning";
  day: number;
  date: string;
  title: string;
  detail: string;
  panchayat_id?: number | null;
  panchayat_name?: string | null;
}

export interface DayInfo {
  day: number;
  date: string;
  weekday: string;
}

export interface BlockSummary {
  block: Region;
  district: Region | null;
  panchayat_count: number;
  active_alerts: number;
  alerts: Alert[];
  run: RunInfo | null;
  days: DayInfo[];
  warnings: Warning[];
}

export interface Insight {
  variable: Variable;
  day: number;
  unit: string;
  min: number;
  max: number;
  block_value: number | null;
  n_panchayats: number;
  text: string;
}

export type GeoJSONGeometry = { type: string; coordinates: unknown };

export interface Feature<P> {
  type: "Feature";
  id?: string | number;
  geometry: GeoJSONGeometry | null;
  properties: P;
}

export interface FeatureCollection<P, M = undefined> {
  type: "FeatureCollection";
  features: Feature<P>[];
  meta?: M;
}

// ---------------------------------------------------------------- S3 panchayat detail
export interface ValuesVsBlock {
  rain_mm: number | null;
  tmax: number | null;
  tmin: number | null;
  rh: number | null;
  wind_kmh: number | null;
}

export interface PanchayatDay {
  day: number;
  date: string;
  weekday: string;
  rain_mm: number;
  rain_min: number | null;
  rain_max: number | null;
  rain_prob_2_5mm: number | null;
  rain_prob_10mm: number | null;
  rain_category: { key: string; label: string };
  tmax: number;
  tmin: number;
  rh: number | null;
  wind_kmh: number | null;
  confidence: Confidence;
  block: ValuesVsBlock;
  diff: ValuesVsBlock;
}

export interface PanchayatForecast {
  panchayat: {
    id: number;
    lgd_code: string;
    name: string;
    name_te: string | null;
    name_hi: string | null;
    elevation_m: number | null;
    registered_farmers: number | null;
    centroid: [number, number] | null;
    block: Region;
    confidence: Confidence;
  };
  run: RunInfo;
  days: PanchayatDay[];
  alerts: Alert[];
  warnings: Warning[];
}

// ---------------------------------------------------------------- S4 advisory
export type Localized = Record<Lang, string>;
export type AdvisoryTag = "avoid" | "prepare" | "do_now";

export interface ExplainCondition {
  metric: string;
  label: Localized;
  op: string;
  unit: string;
  threshold: number;
  actual: number;
}

export interface AdvisoryItem {
  id: string;
  tag: AdvisoryTag;
  urgency: number;
  valid_days: { day: number; date: string }[];
  title: Localized;
  reason: Localized;
  edited?: boolean;
  explain: {
    rule_id: string;
    conditions: ExplainCondition[];
    days_used: {
      day: number;
      date: string;
      weekday: string;
      rain_mm: number;
      rain_prob_10mm: number | null;
      tmax: number;
      rh: number | null;
      wind_kmh: number | null;
    }[];
    note?: string;
  };
}

export interface Advisory {
  id: number;
  panchayat_id: number;
  run_id: number | null;
  crop: string;
  stage: string;
  status: "draft" | "approved" | "sent";
  items: AdvisoryItem[];
  edited_text?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface CropInfo {
  id: string;
  name: Localized;
  icon: string;
  stages: { id: string; name: Localized }[];
}

// ---------------------------------------------------------------- S6 validation
export interface MethodScores {
  rmse: number | null;
  bias: number | null;
  mae: number | null;
  pod: number | null;
  far: number | null;
  csi: number | null;
}

export interface MetricGroup {
  variable: "tmax" | "tmin" | "rain";
  threshold_mm: number | null;
  period: string;
  n_stations: number | null;
  n_samples: number | null;
  n_events: number | null;
  block_baseline?: MethodScores;
  panchayatcast?: MethodScores;
  change_pct: Record<string, number | null>;
}

export interface ValidationStation {
  id: string | number;
  name: string;
  lat: number;
  lon: number;
  distance_km?: number | null;
  source?: string;
  n_days?: number;
  tmax_rmse_block?: number | null;
  tmax_rmse_ours?: number | null;
  rain_mae_block?: number | null;
  rain_mae_ours?: number | null;
}

export interface BacktestEvent {
  id: number;
  date: string;
  station_id: string | number;
  station_name: string | null;
  observed_mm: number;
  block_mm: number;
  ours_mm: number;
  is_placeholder?: boolean;
}

export interface Improvement {
  metric: string;
  change_pct: number | null;
  ci90: [number | null, number | null];
}

export interface ValidationResponse {
  is_placeholder: boolean;
  method_note: string;
  metrics: MetricGroup[];
  backtest_events: BacktestEvent[];
  stations: ValidationStation[];
  summary: {
    period: string;
    method_note: string;
    caveats: string[];
    improvements: Record<string, Improvement>;
    wet_day_counts: { wet_days: number; better: number; worse: number; similar: number };
    scatter_tmax: { obs: number[]; block: number[]; ours: number[] };
  } | null;
  engine_skill: {
    method: string;
    trained_at: string;
    holdout: {
      tmax: { rmse_baseline: number; rmse_model: number };
      tmin: { rmse_baseline: number; rmse_model: number };
      rain: { heavy10_baseline: { csi: number }; heavy10_model: { csi: number } };
    };
  } | null;
}

export interface StationSeries {
  dates: string[];
  [key: string]: (number | null)[] | string[];
}

// ---------------------------------------------------------------- Phase 6b warnings
export type AlertLevel = "yellow" | "orange" | "red";

export interface Warning {
  id: string;
  panchayat_id: number;
  panchayat: { id: number; name: string; name_te: string | null; name_hi: string | null; registered_farmers: number };
  day: number;
  date: string;
  hazard: "rain" | "heat" | "wind";
  event: string;
  level: AlertLevel;
  value: number;
  unit: string;
  probability: number | null;
  confidence: Confidence;
  siren: boolean;
  title: Localized;
  body: Localized;
  actions: Record<Lang, string[]>;
  simulated: boolean;
}

export interface AlertsResponse {
  alerts: Warning[];
  acknowledged: Record<string, { alert_id: string; acknowledged_by: string | null; acknowledged_at: string }>;
  simulation: { version: number; center: number; day: number; block_id: number } | null;
  run: { id: number; source: string; revision: number };
  push_enabled: boolean;
}

export interface DispatchResult {
  alert_id: string;
  push: { subscribers: number; sent: number; failed: number };
  log: { channel: string; recipients: number; delivered: number; status: string }[];
}

// ---------------------------------------------------------------- S5 share
export interface FarmerMessage {
  advisory_id: number;
  lang: Lang;
  channel: "sms" | "whatsapp";
  text: string;
  link: string;
  sms: { encoding: "GSM-7" | "UCS-2"; chars: number; units: number; segments: number; per_segment: number };
  panchayat: { id: number; name: string; name_te: string | null; name_hi: string | null; registered_farmers: number };
}

export interface ShareLogEntry {
  id: number;
  advisory_id: number;
  channel: "sms" | "whatsapp";
  language: Lang;
  recipients: number;
  status: string;
  sent_at: string;
}

export interface Health {
  status: string;
  demo_mode: boolean;
  supabase_configured: boolean;
  serving: string;
  lan_ip: string | null;
}

/** One panchayat-day in the S2 bundle. */
export interface GpDay {
  day: number;
  rain: number;
  rain_min: number | null;
  rain_max: number | null;
  rain_prob_10mm: number | null;
  rain_prob_2_5mm: number | null;
  tmax: number;
  tmin: number;
  rh: number | null;
  wind: number | null;
  confidence: Confidence;
}

export interface GpBundleProps extends Omit<Region, "lgd_code"> {
  elevation_m: number | null;
  days: GpDay[];
}

export interface ForecastBundleMeta {
  block: Region & { mean_elevation_m: number | null };
  block_geometry: GeoJSONGeometry | null;
  run: RunInfo | null;
  days: DayInfo[];
  block_values: ({ day: number } & Record<Variable, number | null>)[];
  units: Record<Variable, string>;
}

export type ForecastBundle = FeatureCollection<GpBundleProps, ForecastBundleMeta>;

export interface DistrictFeatureProps extends Region {
  kind: "district" | "block";
}
