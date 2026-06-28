-- Swing-trade screener tables
-- RLS intentionally disabled — single-user personal tool.
-- Run this in the Supabase SQL editor.

create table if not exists screener_runs (
  id           uuid primary key default gen_random_uuid(),
  status       text not null default 'running',   -- running | done | error
  universe     text not null default 'NIFTY 500',
  total        int  default 0,
  scanned      int  default 0,
  passed       int  default 0,
  error        text,
  started_at   timestamptz default now(),
  finished_at  timestamptz
);

create table if not exists screener_results (
  id                 uuid primary key default gen_random_uuid(),
  run_id             uuid references screener_runs(id) on delete cascade,
  symbol             text not null,
  name               text,
  score              int  not null,
  signals_triggered  jsonb not null default '[]',
  pe_ratio           numeric,
  sector_pe_median   numeric,
  revenue_growth     numeric,
  promoter_holding   numeric,
  promoter_trend     text,            -- up | stable | down | unknown
  last_close         numeric,
  week52_high        numeric,
  week52_low         numeric,
  avg_turnover       numeric,
  created_at         timestamptz default now()
);

create index if not exists screener_results_run_score
  on screener_results (run_id, score desc);

-- Single-user tool — disable RLS so the anon key can read/write freely.
alter table screener_runs    disable row level security;
alter table screener_results disable row level security;
