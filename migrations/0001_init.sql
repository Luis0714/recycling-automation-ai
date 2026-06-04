-- =====================================================================
-- Smart Recycling — initial schema (Phase 1)
-- Apply this once in the Supabase SQL editor (or via supabase db push).
-- Idempotent: safe to re-run.
-- =====================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- stations: forward-looking. One row per physical recycling station.
-- ---------------------------------------------------------------------
create table if not exists stations (
  id          text primary key,
  name        text not null,
  location    text,
  is_active   boolean not null default true,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- detections: every YOLO detection (or manual / stub event) ever made.
-- ---------------------------------------------------------------------
create table if not exists detections (
  id                   uuid primary key default gen_random_uuid(),
  station_id           text references stations(id) on delete set null,
  detected_class       text not null,                  -- raw YOLO class name
  category             text,                           -- Aprovechables | No aprovechables | Orgánicos
  arduino_command      text,                           -- BLANCO | NEGRO | VERDE | ROJO
  confidence           numeric(4,3) not null,          -- 0.000–1.000
  processing_time_ms   integer,
  image_identifier     text,
  source_type          text not null default 'yolo'    -- yolo | manual | stub
                       check (source_type in ('yolo','manual','stub')),
  arduino_delivered    boolean not null default false,
  timestamp            timestamptz not null default now(),
  created_at           timestamptz not null default now()
);

create index if not exists detections_ts_idx          on detections (timestamp desc);
create index if not exists detections_station_ts_idx  on detections (station_id, timestamp desc);
create index if not exists detections_class_idx       on detections (detected_class);
create index if not exists detections_category_idx    on detections (category);

-- ---------------------------------------------------------------------
-- manual_bin_openings: the web "No sé dónde reciclarlo" flow.
-- A row in this table is a durable command; the Python app subscribes
-- to inserts via Supabase Realtime (postgres_changes).
-- ---------------------------------------------------------------------
create table if not exists manual_bin_openings (
  id                   uuid primary key default gen_random_uuid(),
  station_id           text references stations(id) on delete set null,
  bin_type             text not null
                       check (bin_type in ('BLANCO','NEGRO','VERDE','ROJO')),
  status               text not null default 'pending'
                       check (status in ('pending','opened','error','timeout')),
  requested_at         timestamptz not null default now(),
  opened_at            timestamptz,
  latency_ms           integer,
  error_message        text,
  source               text not null default 'web'
                       check (source in ('web','cli','api')),
  client_request_id    text unique                     -- idempotency for retries
);

create index if not exists mbo_station_status_idx  on manual_bin_openings (station_id, status);
create index if not exists mbo_requested_at_idx    on manual_bin_openings (requested_at desc);

-- ---------------------------------------------------------------------
-- bin_status: forward-looking. Activate when fill sensors are added.
-- ---------------------------------------------------------------------
-- create table if not exists bin_status (
--   station_id        text references stations(id) on delete cascade,
--   bin_type          text check (bin_type in ('BLANCO','NEGRO','VERDE','ROJO')),
--   fill_level        integer not null default 0 check (fill_level between 0 and 100),
--   is_open           boolean not null default false,
--   last_emptied_at   timestamptz,
--   updated_at        timestamptz not null default now(),
--   primary key (station_id, bin_type)
-- );

-- ---------------------------------------------------------------------
-- Row Level Security
--   * Web app uses the anon key  →  can SELECT detections/stations,
--     can SELECT/INSERT on manual_bin_openings (with client_request_id
--     idempotency), cannot UPDATE.
--   * Python app uses the service_role key  →  bypasses RLS for writes
--     and UPDATEs.
-- ---------------------------------------------------------------------
alter table detections          enable row level security;
alter table manual_bin_openings enable row level security;
alter table stations            enable row level security;
-- alter table bin_status         enable row level security;  -- when created

drop policy if exists "detections read"      on detections;
drop policy if exists "mbo read"             on manual_bin_openings;
drop policy if exists "mbo insert"           on manual_bin_openings;
drop policy if exists "stations read"        on stations;

create policy "detections read" on detections
  for select using (true);

create policy "mbo read" on manual_bin_openings
  for select using (true);

create policy "mbo insert" on manual_bin_openings
  for insert with check (true);
-- (UPDATE blocked for anon/authenticated — only the service_role can mark
--  a row as opened / error / timeout.)

create policy "stations read" on stations
  for select using (true);

-- ---------------------------------------------------------------------
-- Realtime: the Python app listens to INSERTs on manual_bin_openings.
-- ---------------------------------------------------------------------
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime'
      and tablename = 'manual_bin_openings'
  ) then
    execute 'alter publication supabase_realtime add table manual_bin_openings';
  end if;
end $$;

-- ---------------------------------------------------------------------
-- Seed the default station (matches RAS_STATION_ID in .env).
-- ---------------------------------------------------------------------
insert into stations (id, name, location)
values ('station-001', 'Estación principal', 'Edificio A — Piso 1')
on conflict (id) do nothing;
