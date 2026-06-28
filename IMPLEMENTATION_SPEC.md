# Swing Screener — Implementation Specification

> **Status:** Canonical source of truth.
> **Last updated:** 2026-06-28

---

## 1. What This Is

A **personal swing-trade stock screener** for NSE-listed stocks. It scans the NIFTY 500
universe nightly (and on-demand), scores each stock against technical + fundamental criteria,
and surfaces the top setups in a clean web UI with a sortable results table and a per-stock
candlestick chart.

**Not** investment advice — personal analytical tool, single user.

---

## 2. Architecture

```
Frontend — React + TypeScript + Vite + Tailwind
  @tanstack/react-query · lightweight-charts · lucide-react
            │
            │  fetch /api/*
            ▼
Backend — FastAPI (api/)
  api/main.py → api/routes/screener.py
  api/scheduler.py (APScheduler nightly job)
  core/screeners/swing.py (pure-Python engine)
  core/signals/technical_indicators.py (EMA, RSI, MACD)
  core/data/fetcher.py (yfinance OHLCV + fundamentals)
  core/data/universe.py (NIFTY 500 constituent fetch)
            │
            ▼
Supabase Postgres (no auth, no RLS — single-user tool)
  screener_runs · screener_results
```

**No auth, no disclaimer, no subscription tiers.** App opens directly to the screener.

---

## 3. Screener Logic (`core/screeners/swing.py`)

### Pipeline

1. `get_nifty500()` → ~500 EQ symbols (from NSE Archives CSV, cached 24 h).
2. `fetch_ohlcv_data(symbols, days=400, interval="1d")` — batched yfinance download.
3. **Liquidity filter:** avg daily turnover (close × volume, 20-day) > ₹5 Cr.
4. `fetch_financial_data(survivors)` — parallel ThreadPoolExecutor(10).
5. Build **sector PE medians** across survivors.
6. **Fundamental gate:** PE ≤ sector median (or ≤ 30 fallback) AND revenue growth > 10%.
7. `compute_indicators(df)` → adds EMA9, EMA21, EMA50, RSI14, MACD\_hist, vol\_avg20.
8. Signal detection (see below).
9. **Include only if:** price above 50 EMA AND ≥ 2 signals triggered.
10. **Score** = 1 (above 50 EMA) + number of signals (max 5).
11. Rank by score desc; write to Supabase.

### Technical Signals (4 detectors)

| Signal | Condition |
|---|---|
| `ema_cross_volume` | EMA9 crossed above EMA21 in last 3 bars AND volume > 1.5× 20-day avg |
| `rsi_pullback_up` | RSI(14) dipped to 40–50 in last 3 bars AND RSI turning up |
| `macd_flip` | MACD histogram flipped ≤0 → >0 within last 2 bars |
| `breakout` | Close > prior 4–8 week consolidation high (range < 20%) on volume > 1.5× avg |

### Promoter holding (best-effort)
Via nsetools `get_shareholding_pattern()`; marked `trend = unknown` when unavailable; stocks
are not excluded when data is missing.

---

## 4. Database (Supabase)

Migration: `supabase/migrations/0001_screener.sql`

### `screener_runs`
`id, status (running|done|error), universe, total, scanned, passed, error, started_at, finished_at`

### `screener_results`
`id, run_id (fk → screener_runs), symbol, name, score, signals_triggered (jsonb), pe_ratio,
sector_pe_median, revenue_growth, promoter_holding, promoter_trend, last_close, week52_high,
week52_low, avg_turnover, created_at`

Index: `(run_id, score desc)`

**No RLS** — single-user personal tool. Apply via Supabase SQL editor.

---

## 5. Backend APIs (`/api/screener/*`)

| Endpoint | Description |
|---|---|
| `POST /api/screener/run` | Start a scan. Returns `{run_id}`. Scan runs in background. |
| `GET /api/screener/run/{id}/status` | Poll progress: `{status, scanned, total, passed, error}` |
| `GET /api/screener/results` | Latest completed run's results, ranked by score desc. |
| `GET /api/screener/stock/{symbol}` | 90-day OHLCV + EMA9/21/50 + RSI + MACD hist for chart. |
| `GET /api/health` | `{"status":"ok"}` |

---

## 6. Scheduler (`api/scheduler.py`)

APScheduler `BackgroundScheduler`. Cron: `30 12 * * 1-5` UTC ≈ 18:00 IST (weekdays, after NSE
close). Started in FastAPI `lifespan` hook. **Requires backend process to stay running.**

---

## 7. Frontend (`frontend/src/`)

Single page (`/`) → `pages/SwingScreener.tsx`.

**Components used:**
- `components/SwingChart.tsx` — lightweight-charts candlestick + 3-chart stack (price/EMA, RSI, MACD hist)
- `components/ui/DataTable.tsx` — sortable results table
- `components/ui/Badge.tsx` — signal labels
- `components/ui/Spinner.tsx` — loading states
- `components/ui/MetricCard.tsx` — fundamentals card (reserved for future use)
- `lib/api.ts` — typed fetch wrappers (no auth header)
- `lib/utils.ts` — `fmt()`, `fmtPct()`

**Flow:** Run Scan → button calls `POST /run`, stores `run_id` → polls `/run/{id}/status`
every 2 s while `running` → on `done`, invalidates and loads `/results` → click row → side
panel with `SwingChart` (90-day data from `/stock/{symbol}`).

---

## 8. Key Files

| File | Purpose |
|---|---|
| `api/main.py` | FastAPI app, router, CORS, lifespan |
| `api/db.py` | `get_supabase()` — anon-key client (no auth) |
| `api/routes/screener.py` | All 4 screener endpoints + background scan task |
| `api/scheduler.py` | APScheduler nightly job |
| `core/screeners/swing.py` | Full scan pipeline + signal detectors |
| `core/data/universe.py` | NIFTY 500 constituent fetch (NSE Archives, cached) |
| `core/data/fetcher.py` | `fetch_ohlcv_data`, `fetch_financial_data` |
| `core/signals/technical_indicators.py` | `EMA`, `RSI`, `MACD` |
| `supabase/migrations/0001_screener.sql` | Table DDL (apply manually in Supabase SQL editor) |
| `frontend/src/pages/SwingScreener.tsx` | Main page |
| `frontend/src/components/SwingChart.tsx` | lightweight-charts chart component |

---

## 9. Local Development

```bash
# Backend
source venv/bin/activate
uvicorn api.main:app --reload

# Frontend
cd frontend
npm run dev        # port 3000, proxies /api → localhost:8000
```

Apply `supabase/migrations/0001_screener.sql` in the Supabase SQL editor once before first run.

---

## 10. Engineering Guidelines

1. **No auth anywhere** — `api/db.py` uses the anon key; tables have no RLS.
2. **Keep `core/` pure Python** — no FastAPI imports.
3. **Routes are thin adapters** — all scan logic lives in `core/screeners/swing.py`.
4. **Promoter data is best-effort** — never exclude a stock solely because nsetools failed.
5. **Layout:** page containers use `h-[calc(100vh-Xpx)]`, never `h-full` (resolves to 0 in
   min-height parents).
6. **Git:** commit/push only when asked; omit Co-Authored-By trailer.
