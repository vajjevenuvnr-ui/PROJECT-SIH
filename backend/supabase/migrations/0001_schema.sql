-- Kshetra schema (Supabase / Postgres 15 + PostGIS)
-- Run once in the Supabase SQL editor, or: python -m scripts.seed_demo --apply
-- All geometries are EPSG:4326. LGD codes are the official join keys.

create extension if not exists postgis;

-- ---------------------------------------------------------------------------
-- Administrative hierarchy: State > District > Block (mandal) > Gram Panchayat
-- ---------------------------------------------------------------------------
create table if not exists states (
  id          serial primary key,
  lgd_code    text unique not null,
  name        text not null,
  name_te     text,
  name_hi     text
);

create table if not exists districts (
  id          serial primary key,
  lgd_code    text unique not null,
  state_id    int not null references states(id) on delete cascade,
  name        text not null,
  name_te     text,
  name_hi     text,
  geom        geometry(MultiPolygon, 4326)
);

create table if not exists blocks (
  id                serial primary key,
  lgd_code          text unique not null,
  district_id       int not null references districts(id) on delete cascade,
  name              text not null,
  name_te           text,
  name_hi           text,
  mean_elevation_m  real,
  geom              geometry(MultiPolygon, 4326)
);

create table if not exists panchayats (
  id                  serial primary key,
  lgd_code            text unique not null,
  block_id            int not null references blocks(id) on delete cascade,
  name                text not null,
  name_te             text,
  name_hi             text,
  elevation_m         real,
  registered_farmers  int default 0,
  geom                geometry(MultiPolygon, 4326),
  centroid            geometry(Point, 4326)
);

-- ---------------------------------------------------------------------------
-- Forecasts
-- ---------------------------------------------------------------------------
create table if not exists forecast_runs (
  id          serial primary key,
  issued_at   timestamptz not null,
  source      text not null check (source in ('openmeteo-imd-format', 'imd', 'replay', 'seed')),
  status      text not null default 'ok' check (status in ('ok', 'stale', 'failed', 'running')),
  duration_s  real,
  notes       text,
  created_at  timestamptz not null default now()
);

-- Mirrors the fields of an IMD agromet (GKMS) block bulletin.
create table if not exists block_forecasts (
  id          bigserial primary key,
  run_id      int not null references forecast_runs(id) on delete cascade,
  block_id    int not null references blocks(id) on delete cascade,
  day         smallint not null check (day between 1 and 5),
  date        date not null,
  rain_mm     real,
  tmax        real,
  tmin        real,
  rh_max      real,
  rh_min      real,
  wind_kmh    real,
  wind_dir    real,
  cloud_okta  smallint,
  unique (run_id, block_id, day)
);

create table if not exists panchayat_forecasts (
  id               bigserial primary key,
  run_id           int not null references forecast_runs(id) on delete cascade,
  panchayat_id     int not null references panchayats(id) on delete cascade,
  day              smallint not null check (day between 1 and 5),
  date             date not null,
  rain_mm          real,
  rain_min         real,
  rain_max         real,
  rain_prob_2_5mm  real check (rain_prob_2_5mm between 0 and 1),
  rain_prob_10mm   real check (rain_prob_10mm between 0 and 1),
  tmax             real,
  tmin             real,
  rh               real,
  wind_kmh         real,
  confidence       text not null check (confidence in ('high', 'medium', 'low')),
  model_spread     real,
  unique (run_id, panchayat_id, day)
);

-- ---------------------------------------------------------------------------
-- Advisories and delivery
-- ---------------------------------------------------------------------------
create table if not exists profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  name        text,
  role        text not null default 'officer' check (role in ('officer', 'admin')),
  block_ids   int[] default '{}'
);

create table if not exists advisories (
  id            bigserial primary key,
  panchayat_id  int not null references panchayats(id) on delete cascade,
  run_id        int references forecast_runs(id) on delete set null,
  crop          text not null,
  stage         text not null,
  items         jsonb not null default '[]',
  status        text not null default 'draft' check (status in ('draft', 'approved', 'sent')),
  edited_text   jsonb,
  approved_by   uuid references auth.users(id),
  created_at    timestamptz not null default now()
);

create table if not exists share_log (
  id            bigserial primary key,
  advisory_id   bigint not null references advisories(id) on delete cascade,
  channel       text not null check (channel in ('sms', 'whatsapp')),
  language      text not null check (language in ('te', 'hi', 'en')),
  recipients    int not null default 0,
  status        text not null default 'Delivered (simulated)',
  sent_at       timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Ground truth and validation
-- ---------------------------------------------------------------------------
create table if not exists aws_stations (
  id                serial primary key,
  code              text unique not null,
  name              text not null,
  lat               double precision not null,
  lon               double precision not null,
  elevation_m       real,
  panchayat_id      int references panchayats(id) on delete set null,
  used_in_training  boolean not null default false,
  geom              geometry(Point, 4326)
);

-- qc_flag: 0 = raw, 1 = filled, 2 = removed (Data Strategy 5.1)
create table if not exists observations (
  id          bigserial primary key,
  station_id  int not null references aws_stations(id) on delete cascade,
  date        date not null,
  rain_mm     real,
  tmax        real,
  tmin        real,
  rh          real,
  wind_kmh    real,
  qc_flag     smallint not null default 0 check (qc_flag in (0, 1, 2)),
  unique (station_id, date)
);

create table if not exists validation_metrics (
  id              serial primary key,
  variable        text not null,
  period          text not null,
  method          text not null check (method in ('block_baseline', 'panchayatcast')),
  threshold_mm    real,
  rmse            real,
  bias            real,
  mae             real,
  pod             real,
  far             real,
  csi             real,
  n_stations      int,
  n_samples       int,
  is_placeholder  boolean not null default false,
  computed_at     timestamptz not null default now()
);

create table if not exists backtest_events (
  id              serial primary key,
  date            date not null,
  station_id      int references aws_stations(id) on delete cascade,
  observed_mm     real,
  block_mm        real,
  ours_mm         real,
  note            text,
  is_placeholder  boolean not null default false
);

-- Farmer "Did it rain today?" (S7)
create table if not exists rain_feedback (
  id            bigserial primary key,
  panchayat_id  int not null references panchayats(id) on delete cascade,
  date          date not null default current_date,
  rained        boolean not null,
  created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
create index if not exists districts_geom_idx on districts using gist (geom);
create index if not exists blocks_geom_idx on blocks using gist (geom);
create index if not exists panchayats_geom_idx on panchayats using gist (geom);
create index if not exists panchayats_block_idx on panchayats (block_id);
create index if not exists aws_geom_idx on aws_stations using gist (geom);
create index if not exists pf_run_day_idx on panchayat_forecasts (run_id, day);
create index if not exists pf_panchayat_idx on panchayat_forecasts (panchayat_id);
create index if not exists bf_block_idx on block_forecasts (block_id, run_id);
create index if not exists obs_station_date_idx on observations (station_id, date);
create index if not exists feedback_gp_date_idx on rain_feedback (panchayat_id, date);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- The backend uses the service-role key (bypasses RLS). These policies
-- govern direct access with the anon / authenticated keys.
-- ---------------------------------------------------------------------------
alter table states enable row level security;
alter table districts enable row level security;
alter table blocks enable row level security;
alter table panchayats enable row level security;
alter table forecast_runs enable row level security;
alter table block_forecasts enable row level security;
alter table panchayat_forecasts enable row level security;
alter table aws_stations enable row level security;
alter table observations enable row level security;
alter table validation_metrics enable row level security;
alter table backtest_events enable row level security;
alter table rain_feedback enable row level security;
alter table advisories enable row level security;
alter table share_log enable row level security;
alter table profiles enable row level security;

-- Public read on regions, forecasts and validation
do $$
declare t text;
begin
  foreach t in array array['states','districts','blocks','panchayats','forecast_runs','block_forecasts',
                           'panchayat_forecasts','aws_stations','observations','validation_metrics','backtest_events']
  loop
    execute format('drop policy if exists "public read" on %I', t);
    execute format('create policy "public read" on %I for select using (true)', t);
  end loop;
end $$;

-- Farmers can submit rain feedback without logging in
drop policy if exists "public insert feedback" on rain_feedback;
create policy "public insert feedback" on rain_feedback for insert with check (true);
drop policy if exists "officer read feedback" on rain_feedback;
create policy "officer read feedback" on rain_feedback for select to authenticated using (true);

-- Officers manage advisories and the share log
create or replace function is_officer() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where id = auth.uid() and role in ('officer', 'admin'));
$$;

drop policy if exists "officer all advisories" on advisories;
create policy "officer all advisories" on advisories for all to authenticated
  using (is_officer()) with check (is_officer());
drop policy if exists "officer all share_log" on share_log;
create policy "officer all share_log" on share_log for all to authenticated
  using (is_officer()) with check (is_officer());

-- Users read their own profile
drop policy if exists "own profile" on profiles;
create policy "own profile" on profiles for select to authenticated using (id = auth.uid());
