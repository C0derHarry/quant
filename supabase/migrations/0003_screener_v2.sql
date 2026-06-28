-- Swing screener v2 schema migration
-- Run in Supabase SQL editor before the first v2 scan.
-- All new columns are nullable — existing rows remain valid.

ALTER TABLE screener_results
  ADD COLUMN IF NOT EXISTS setup_type    TEXT,
  ADD COLUMN IF NOT EXISTS rs_ratio      FLOAT8,
  ADD COLUMN IF NOT EXISTS rs_rank       FLOAT8,
  ADD COLUMN IF NOT EXISTS trend_score   SMALLINT,
  ADD COLUMN IF NOT EXISTS adx           FLOAT8,
  ADD COLUMN IF NOT EXISTS entry_pivot   FLOAT8,
  ADD COLUMN IF NOT EXISTS stop          FLOAT8,
  ADD COLUMN IF NOT EXISTS target        FLOAT8,
  ADD COLUMN IF NOT EXISTS rr            FLOAT8,
  ADD COLUMN IF NOT EXISTS atr           FLOAT8,
  ADD COLUMN IF NOT EXISTS earnings_flag BOOLEAN DEFAULT false;
