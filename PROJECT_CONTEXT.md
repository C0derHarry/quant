# Swing Screener — Project Context

> Quick-start brief. Full detail: **IMPLEMENTATION_SPEC.md**.

## What it is
A **personal swing-trade stock screener** for NSE. Scans NIFTY 500 nightly + on demand,
scores each stock on 4 technical signals + fundamental gate, and surfaces top setups in a
UI with sortable table and candlestick chart (lightweight-charts).

## Stack
- **Frontend:** React + TS + Vite + Tailwind; `@tanstack/react-query`; `lightweight-charts` (charts)
- **Backend:** FastAPI (`api/`). Thin routes over pure-Python `core/`. APScheduler for nightly job.
- **Data:** yfinance (OHLCV + fundamentals), nsetools (promoter data, best-effort), NSE Archives CSV (universe).
- **DB:** Supabase Postgres. **No auth, no RLS** — single-user tool. Two tables: `screener_runs`, `screener_results`.

## Key files
- `core/screeners/swing.py` — full scan pipeline (universe → liquidity → fundamentals → signals → score)
- `core/data/universe.py` — NIFTY 500 constituent fetch (24 h cached)
- `core/data/fetcher.py` — `fetch_ohlcv_data`, `fetch_financial_data`
- `core/signals/technical_indicators.py` — `EMA`, `RSI`, `MACD` (reused)
- `api/routes/screener.py` — `POST /run`, `GET /run/{id}/status`, `GET /results`, `GET /stock/{sym}`
- `api/scheduler.py` — nightly APScheduler job (12:30 UTC ≈ 18:00 IST weekdays)
- `api/db.py` — `get_supabase()` anon-key client
- `frontend/src/pages/SwingScreener.tsx` — single page: run button + table + side panel
- `frontend/src/components/SwingChart.tsx` — candlestick + RSI + MACD panels (lightweight-charts v4)
- `supabase/migrations/0001_screener.sql` — apply once in Supabase SQL editor

## Screener criteria
- **Liquidity filter:** avg daily turnover > ₹5 Cr (20-day)
- **Fundamental gate:** PE ≤ sector median (or ≤ 30), revenue growth > 10%
- **Price gate:** above 50 EMA (long-only)
- **4 technical signals** (≥ 2 required): EMA cross + volume spike, RSI 40–50 pullback turning up,
  MACD histogram flip, 4–8 week consolidation breakout on volume
- **Score:** 1–5 (1 for above-50-EMA + 1 per signal)

## Conventions / gotchas
- No auth anywhere. Open directly to `/`.
- `core/` must not import FastAPI.
- Layout: `h-[calc(100vh-Xpx)]` not `h-full`.
- Promoter data is best-effort — stocks pass when nsetools is unavailable.
- Nightly scan requires backend process to stay running.
- Git: commit/push only when asked; omit Co-Authored-By trailer.
