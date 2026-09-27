-- Phase 10: crop profiles per panchayat.
create table if not exists crop_profiles (
  panchayat_id  int primary key references panchayats(id) on delete cascade,
  crop          text not null,
  sowing_date   date not null,
  is_default    boolean not null default false,
  updated_at    timestamptz not null default now()
);
alter table crop_profiles enable row level security;
drop policy if exists "public read profiles" on crop_profiles;
create policy "public read profiles" on crop_profiles for select using (true);
drop policy if exists "officer write profiles" on crop_profiles;
create policy "officer write profiles" on crop_profiles for all to authenticated using (is_officer()) with check (is_officer());
