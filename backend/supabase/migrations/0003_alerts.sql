-- Phase 6b: extreme-weather alerts (acknowledgements, dispatch log, Web Push subscriptions).

create table if not exists alert_acks (
  alert_id         text primary key,          -- "<run>.<revision>-<panchayat>-<day>-<hazard>"
  acknowledged_by  text,
  acknowledged_at  timestamptz not null default now()
);

create table if not exists alert_dispatch_log (
  id            bigserial primary key,
  alert_id      text not null,
  panchayat_id  int references panchayats(id) on delete cascade,
  channel       text not null check (channel in ('push', 'sms_alert', 'voice_alert')),
  language      text,
  recipients    int not null default 0,
  delivered     int not null default 0,
  status        text not null,
  sent_at       timestamptz not null default now()
);

-- Farmers opt in on the public page; no login, so no personal data beyond the browser endpoint.
create table if not exists push_subscriptions (
  id            bigserial primary key,
  endpoint      text unique not null,
  p256dh        text not null,
  auth          text not null,
  panchayat_id  int not null references panchayats(id) on delete cascade,
  lang          text not null default 'te' check (lang in ('te', 'hi', 'en')),
  created_at    timestamptz not null default now()
);

create index if not exists dispatch_alert_idx on alert_dispatch_log (alert_id);
create index if not exists push_gp_idx on push_subscriptions (panchayat_id);

alter table alert_acks enable row level security;
alter table alert_dispatch_log enable row level security;
alter table push_subscriptions enable row level security;

-- Officers read/write acknowledgements and the dispatch log; the backend (service role) bypasses RLS.
drop policy if exists "officer all acks" on alert_acks;
create policy "officer all acks" on alert_acks for all to authenticated using (is_officer()) with check (is_officer());
drop policy if exists "officer all dispatch" on alert_dispatch_log;
create policy "officer all dispatch" on alert_dispatch_log for all to authenticated using (is_officer()) with check (is_officer());
-- Subscriptions are written only through the backend (service role); no public policy.
