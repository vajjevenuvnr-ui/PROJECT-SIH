-- Farmer contacts: imported by officers (CSV / Excel) or self-registered on the farmer page with consent.
-- Personal data: no public read policy; only the backend (service role) reads/writes. The API masks numbers.
create table if not exists farmers (
  id            bigserial primary key,
  panchayat_id  int not null references panchayats(id) on delete cascade,
  name          text,
  mobile        text not null check (mobile ~ '^[6-9][0-9]{9}$'),
  crop          text,
  language      text not null default 'te' check (language in ('te', 'hi', 'en')),
  source        text not null default 'upload' check (source in ('upload', 'self')),
  consent_at    timestamptz,
  active        boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (panchayat_id, mobile)
);
create index if not exists farmers_panchayat_idx on farmers (panchayat_id) where active;
alter table farmers enable row level security;
-- no policies: anon / authenticated clients cannot read phone numbers directly.
